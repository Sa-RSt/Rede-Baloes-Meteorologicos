#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>
#include <math.h>

// Defina como 1 e instale Adafruit BMP280, Adafruit DHT e Unified Sensor para ativar.
#define HABILITAR_SENSORES_REAIS 0
#if HABILITAR_SENSORES_REAIS
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <DHT.h>
#endif

constexpr int PIN_BMP280_SDA = 21;
constexpr int PIN_BMP280_SCL = 22;
constexpr int PIN_DHT11_DATA = 27;
constexpr float PRESSAO_NIVEL_MAR_HPA = 1013.25f;

#if HABILITAR_SENSORES_REAIS
Adafruit_BMP280 bmp280;
DHT dht11(PIN_DHT11_DATA, DHT11);
bool bmp280Disponivel = false;
bool dht11Disponivel = false;
#endif

constexpr int PIN_SCK  = 18;
constexpr int PIN_MISO = 19;
constexpr int PIN_MOSI = 23;
constexpr int PIN_NSS  = 5;
constexpr int PIN_RST  = 14;
constexpr int PIN_DIO0 = 26;

// Frequência de comunicação LoRa
constexpr long FREQUENCIA_LORA = 915500000L;

// Intervalo de transmissão: 20 segundos
constexpr unsigned long INTERVALO_MS = 20000UL;

// Identificador único do balão
constexpr char ID_BALAO[] = "BALAO01";

// true  = dados simulados
// false = sensores reais
constexpr bool MODO_SIMULACAO = true;

struct DadosMeteorologicos {
  float temperatura; // Celsius
  float umidade;     // %
  float pressao;     // hPa
  float altitude;    // metros
  float bateria;     // volts
};

uint32_t sequencia = 0;
unsigned long ultimaTentativa = 0;

void inicializarSensores() {
#if HABILITAR_SENSORES_REAIS
  Wire.begin(PIN_BMP280_SDA, PIN_BMP280_SCL);
  bmp280Disponivel = bmp280.begin(0x76);
  if (!bmp280Disponivel) bmp280Disponivel = bmp280.begin(0x77);
  Serial.println(bmp280Disponivel ? "[OK] BMP280 inicializado." : "[ERRO] BMP280 nao encontrado (0x76/0x77).");
  dht11.begin();
  dht11Disponivel = true;
  Serial.println("[OK] DHT11 inicializado.");
#endif
}

float lerTemperatura() {
#if HABILITAR_SENSORES_REAIS
  if (!bmp280Disponivel) return NAN;
  return bmp280.readTemperature();
#else
  return NAN;
#endif
}

float lerUmidade() {
#if HABILITAR_SENSORES_REAIS
  if (!dht11Disponivel) return NAN;
  return dht11.readHumidity();
#else
  return NAN;
#endif
}

float lerTemperaturaDHT11() {
#if HABILITAR_SENSORES_REAIS
  if (!dht11Disponivel) return NAN;
  return dht11.readTemperature();
#else
  return NAN;
#endif
}

float lerPressao() {
#if HABILITAR_SENSORES_REAIS
  if (!bmp280Disponivel) return NAN;
  return bmp280.readPressure() / 100.0f;
#else
  return NAN;
#endif
}

float lerAltitude() {
#if HABILITAR_SENSORES_REAIS
  if (!bmp280Disponivel) return NAN;
  return bmp280.readAltitude(PRESSAO_NIVEL_MAR_HPA);
#else
  return NAN;
#endif
}

float lerBateria() {
  // TODO: medir tensão da bateria
  // Para o ADC, utilizar divisor de tensão apropriado.

  return NAN;
}

// Gera valores fictícios para testar a comunicação.
void gerarDadosSimulados(DadosMeteorologicos &dados) {
  dados.temperatura = random(150, 320) / 10.0f;

  dados.umidade = random(350, 850) / 10.0f;

  dados.altitude = 100.0f + (sequencia % 100) * 5.0f;

  // Aproximação barométrica para simulação
  dados.pressao = 1013.25f * powf(1.0f - dados.altitude / 44330.0f, 5.255f);

  dados.bateria = 3.70f + random(0, 50) / 100.0f;
}

// Decide entre simulação e sensores reais.
bool obterLeituras(DadosMeteorologicos &dados) {

  if (MODO_SIMULACAO) {
    gerarDadosSimulados(dados);
  } else {
    dados.temperatura = lerTemperatura();
    dados.umidade = lerUmidade();
    dados.pressao = lerPressao();
    dados.altitude = lerAltitude();
    dados.bateria = lerBateria();
  }

  // Verifica se todos os valores são válidos.
  // Evita transmitir leituras ausentes ou absurdas.

  return isfinite(dados.temperatura) &&
         isfinite(dados.umidade) &&
         isfinite(dados.pressao) &&
         isfinite(dados.altitude) &&
         isfinite(dados.bateria) &&
         dados.temperatura >= -100.0f &&
         dados.temperatura <= 100.0f &&
         dados.umidade >= 0.0f &&
         dados.umidade <= 100.0f &&
         dados.pressao >= 100.0f &&
         dados.pressao <= 1200.0f &&
         dados.altitude >= -500.0f &&
         dados.altitude <= 60000.0f &&
         dados.bateria >= 0.0f &&
         dados.bateria <= 5.0f;
}

bool transmitirDados(const DadosMeteorologicos &dados) {
  // Formato CSV:
  // ID,sequencia,temperatura,umidade,pressao,altitude,bateria

  String pacote = String(ID_BALAO) + "," +
                  String(sequencia) + "," +
                  String(dados.temperatura, 2) + "," +
                  String(dados.umidade, 2) + "," +
                  String(dados.pressao, 2) + "," +
                  String(dados.altitude, 2) + "," +
                  String(dados.bateria, 2);

  // Inicia transmissão
  if (!LoRa.beginPacket()) {
    Serial.println("[LoRa] Falha ao iniciar pacote.");
    return false;
  }

  LoRa.print(pacote);

  // Finaliza e transmite o pacote
  if (LoRa.endPacket() != 1) {
    Serial.println("[LoRa] Falha na transmissao.");
    return false;
  }

  Serial.print("[LoRa] Enviado: ");
  Serial.println(pacote);

  return true;
}

void setup() {

  Serial.begin(115200);
  delay(300);

  randomSeed(esp_random());

  Serial.println("==============================");
  Serial.println(" BALAO METEOROLOGICO - ESP32");
  Serial.println("==============================");

  if (!MODO_SIMULACAO) inicializarSensores();
  // Configura comunicação SPI
  SPI.begin(
    PIN_SCK,
    PIN_MISO,
    PIN_MOSI,
    PIN_NSS
  );

  // Configura pinos do módulo LoRa
  LoRa.setPins(
    PIN_NSS,
    PIN_RST,
    PIN_DIO0
  );

  // Inicializa rádio LoRa
  if (!LoRa.begin(FREQUENCIA_LORA)) {

    Serial.println("[ERRO] Falha ao iniciar LoRa!");

    while (true) {
      delay(1000);
    }
  }

  // Parametros da comunicação
  LoRa.setSpreadingFactor(9);
  LoRa.setSignalBandwidth(125000);
  LoRa.setCodingRate4(5);
  LoRa.setSyncWord(0x12);
  LoRa.setTxPower(10);
  LoRa.enableCrc();

  Serial.println("[OK] LoRa inicializado!");

  if (MODO_SIMULACAO) {
    Serial.println("[INFO] Modo simulacao ativo.");
  } else {
    Serial.println("[INFO] Modo sensores reais ativo.");
  }

  // Permite primeira transmissão imediata
  ultimaTentativa = millis() - INTERVALO_MS;
}

void loop() {

  // Verifica o intervalo de transmissão
  if (millis() - ultimaTentativa < INTERVALO_MS) {
    delay(10);
    return;
  }

  ultimaTentativa = millis();

  DadosMeteorologicos dados;

  // Obtém as leituras
  if (!obterLeituras(dados)) {

    Serial.println("[ERRO] Leituras invalidas.");
    Serial.println("Nenhum pacote enviado.");

    return;
  }

  // Transmite via LoRa
  if (transmitirDados(dados)) {
    sequencia++;
  }
}
