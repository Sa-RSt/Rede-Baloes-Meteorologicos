#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>
#include <math.h>

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

// TODO: implementar as leituras quando os sensores forem definidos.

float lerTemperatura() {
  // TODO: ler temperatura do sensor
  // Exemplo: return sensor.readTemperature();

  return NAN;
}

float lerUmidade() {
  // TODO: ler umidade relativa do sensor

  return NAN;
}

float lerPressao() {
  // TODO: ler pressao atmosferica em hPa

  return NAN;
}

float lerAltitude() {
  // TODO: obter altitude por GPS ou calculo barometrico

  return NAN;
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

  // TODO: inicializar sensores reais aqui.
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