/*
 * 玄機閣 · BLE 电子罗盘固件（ESP32 + QMC5883L + MPU6050）
 * 功能：倾角补偿磁航向 → 蓝牙 BLE（Nordic UART 服务）推送 JSON → 网页端接收
 *       BOOT 键长按 3 秒进入校准（∞ 字摇晃 15 秒），校准值存 NVS 断电不丢
 * 输出：5Hz，每行 {"h":航向°,"p":俯仰°,"r":横滚°,"c":校准状态}\n
 *
 * 接线（详见 wiring.svg）：
 *   QMC5883L / MPU6050    ESP32 DevKit
 *   VCC        →          3V3
 *   GND        →          GND
 *   SDA        →          GPIO21
 *   SCL        →          GPIO22
 *   BOOT 按钮即板载 IO0 键；LED 用板载 GPIO2
 *
 * 零外部库：仅 Wire / BLE / Preferences（ESP32 Arduino 自带）
 * 烧录：Arduino IDE → 开发板 "ESP32 Dev Module" → 上传
 */

#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Preferences.h>

/* ---------- 引脚与地址 ---------- */
#define PIN_SDA     21
#define PIN_SCL     22
#define PIN_BTN     0        /* BOOT 键 */
#define PIN_LED     2        /* 板载 LED */
#define QMC_ADDR    0x0D
#define MPU_ADDR    0x68

/* Nordic UART Service（Web Bluetooth 标准通道） */
#define NUS_SVC   "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_RX    "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   /* 手机 → 罗盘 */
#define NUS_TX    "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   /* 罗盘 → 手机 */

/* 磁偏角（度，东偏为正；可被 BLE 指令 "D=7.5" 修改并存 NVS） */
float g_declination = 0.0f;
/* 安装方向翻转（模块平贴盘面、天线朝上时一般不用动；倒装改 1） */
#define FLIP_Z 0

Preferences prefs;
BLECharacteristic *txChar;
bool deviceConnected = false;

/* ---------- 校准数据 ---------- */
struct Cal { float ox, oy, oz, sx, sy, sz; } g_cal = {0, 0, 0, 1, 1, 1};
bool g_calibrated = false;

void loadCal() {
  prefs.begin("luopan", true);
  g_declination = prefs.getFloat("decl", 0.0f);
  size_t n = prefs.getBytesLength("cal");
  if (n == sizeof(g_cal)) {
    prefs.getBytes("cal", &g_cal, sizeof(g_cal));
    g_calibrated = true;
  }
  prefs.end();
}
void saveCal() {
  prefs.begin("luopan", false);
  prefs.putBytes("cal", &g_cal, sizeof(g_cal));
  prefs.putFloat("decl", g_declination);
  prefs.end();
}

/* ---------- 传感器原始读数 ---------- */
bool qmcRead(float &mx, float &my, float &mz) {
  uint8_t raw[6];
  Wire.beginTransmission(QMC_ADDR);
  Wire.write(0x00);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(QMC_ADDR, (uint8_t)6) != 6) return false;
  for (int i = 0; i < 6; i++) raw[i] = Wire.read();
  int16_t x = (int16_t)(raw[1] << 8 | raw[0]);
  int16_t y = (int16_t)(raw[3] << 8 | raw[2]);
  int16_t z = (int16_t)(raw[5] << 8 | raw[4]);
  mx = x / 3000.0f * 100.0f;          /* ±8G 量程 → 微特斯拉近似 */
  my = y / 3000.0f * 100.0f;
  mz = z / 3000.0f * 100.0f;
#if FLIP_Z
  mz = -mz;
#endif
  return true;
}
bool mpuRead(float &ax, float &ay, float &az) {
  uint8_t raw[6];
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(MPU_ADDR, (uint8_t)6) != 6) return false;
  for (int i = 0; i < 6; i++) raw[i] = Wire.read();
  ax = (int16_t)(raw[0] << 8 | raw[1]) / 16384.0f;   /* ±2g */
  ay = (int16_t)(raw[2] << 8 | raw[3]) / 16384.0f;
  az = (int16_t)(raw[4] << 8 | raw[5]) / 16384.0f;
  return true;
}

/* ---------- 倾角补偿航向 ---------- */
float headingDeg(float mx, float my, float mz, float ax, float ay, float az) {
  float pitch = atan2f(-ax, sqrtf(ay * ay + az * az));
  float roll  = atan2f(ay, az);
  float Xh =  mx * cosf(pitch) + mz * sinf(pitch);
  float Yh =  mx * sinf(roll) * sinf(pitch) + my * cosf(roll)
            - mz * sinf(roll) * cosf(pitch);
  float h = atan2f(Yh, Xh) * 57.2957795f + g_declination;
  while (h < 0) h += 360.0f;
  while (h >= 360) h -= 360.0f;
  return h;
}

/* ---------- 校准流程：∞ 字摇晃采 min/max ---------- */
void runCalibration() {
  digitalWrite(PIN_LED, HIGH);
  float mn[3] = {1e9, 1e9, 1e9}, mx_[3] = {-1e9, -1e9, -1e9};
  float mx, my, mz;
  uint32_t t0 = millis();
  while (millis() - t0 < 15000) {                 /* 15 秒 */
    digitalWrite(PIN_LED, (millis() / 250) % 2);  /* 快闪 */
    if (qmcRead(mx, my, mz)) {
      float v[3] = {mx, my, mz};
      for (int i = 0; i < 3; i++) { mn[i] = fminf(mn[i], v[i]); mx_[i] = fmaxf(mx_[i], v[i]); }
    }
    delay(10);
  }
  g_cal.ox = (mn[0] + mx_[0]) / 2;  g_cal.oy = (mn[1] + mx_[1]) / 2;  g_cal.oz = (mn[2] + mx_[2]) / 2;
  float rx = (mx_[0] - mn[0]) / 2, ry = (mx_[1] - mn[1]) / 2, rz = (mx_[2] - mn[2]) / 2;
  float rAvg = (rx + ry + rz) / 3;
  if (rx > 1 && ry > 1 && rz > 1) {               /* 采样充分才生效 */
    g_cal.sx = rAvg / rx; g_cal.sy = rAvg / ry; g_cal.sz = rAvg / rz;
    g_calibrated = true;
    saveCal();
  }
  digitalWrite(PIN_LED, g_calibrated);
}

/* ---------- BLE 回调 ---------- */
class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer *) override { deviceConnected = true; digitalWrite(PIN_LED, HIGH); }
  void onDisconnect(BLEServer *s) override {
    deviceConnected = false; digitalWrite(PIN_LED, LOW);
    s->getAdvertising()->start();
  }
};
class RxCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String s = String((char *)c->getData());
    if (s.startsWith("D=")) {                     /* 设置磁偏角 */
      g_declination = s.substring(2).toFloat();
      saveCal();
    } else if (s.startsWith("CAL")) {             /* 远程触发校准 */
      runCalibration();
    }
  }
};

/* ---------- 初始化 ---------- */
void setup() {
  Serial.begin(115200);
  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  /* QMC5883L：连续模式 / ±8G / 200Hz / OSR512 */
  Wire.beginTransmission(QMC_ADDR);
  Wire.write(0x0B); Wire.write(0x01); Wire.endTransmission();
  Wire.beginTransmission(QMC_ADDR);
  Wire.write(0x09); Wire.write(0x1D); Wire.endTransmission();
  /* MPU6050：唤醒 / ±2g */
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B); Wire.write(0x00); Wire.endTransmission();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x1C); Wire.write(0x00); Wire.endTransmission();

  loadCal();

  BLEDevice::init("XuanJi-LuoPan");
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());
  BLEService *svc = server->createService(NUS_SVC);
  txChar = svc->createCharacteristic(NUS_TX, BLECharacteristic::PROPERTY_NOTIFY);
  txChar->addDescriptor(new BLE2902());
  BLECharacteristic *rx = svc->createCharacteristic(NUS_RX, BLECharacteristic::PROPERTY_WRITE);
  rx->setCallbacks(new RxCB());
  svc->start();
  server->getAdvertising()->addServiceUUID(NUS_SVC);
  server->getAdvertising()->start();

  /* 上电：长按 BOOT 3 秒进校准 */
  uint32_t t = millis();
  while (digitalRead(PIN_BTN) == LOW && millis() - t < 3000) delay(10);
  if (digitalRead(PIN_BTN) == LOW) runCalibration();
  digitalWrite(PIN_LED, g_calibrated);
}

/* ---------- 主循环：5Hz 推送 ---------- */
void loop() {
  static uint32_t lastBtn = 0;
  /* 运行中长按 3 秒也可重新校准 */
  if (digitalRead(PIN_BTN) == LOW) {
    if (!lastBtn) lastBtn = millis();
    if (millis() - lastBtn > 3000) { lastBtn = 0; runCalibration(); }
  } else lastBtn = 0;

  static uint32_t tSend = 0;
  if (millis() - tSend >= 200) {
    tSend = millis();
    float mx, my, mz, ax, ay, az;
    if (qmcRead(mx, my, mz) && mpuRead(ax, ay, az)) {
      mx = (mx - g_cal.ox) * g_cal.sx;
      my = (my - g_cal.oy) * g_cal.sy;
      mz = (mz - g_cal.oz) * g_cal.sz;
      float h = headingDeg(mx, my, mz, ax, ay, az);
      float p = atan2f(-ax, sqrtf(ay * ay + az * az)) * 57.2957795f;
      float r = atan2f(ay, az) * 57.2957795f;
      char line[96];
      snprintf(line, sizeof(line), "{\"h\":%.1f,\"p\":%.1f,\"r\":%.1f,\"c\":%d}\n",
               h, p, r, g_calibrated ? 1 : 0);
      if (deviceConnected) {
        txChar->setValue((uint8_t *)line, strlen(line));
        txChar->notify();
      }
      Serial.print(line);
    }
  }
  delay(5);
}
