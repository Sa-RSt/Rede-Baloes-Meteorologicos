#include <Arduino.h>
#include <SPI.h>
#include <math.h>
#include <string.h>

// Defina como 1 e instale Adafruit BMP280, Adafruit DHT e Unified Sensor para ativar.
#define HABILITAR_SENSORES_REAIS 1
#if HABILITAR_SENSORES_REAIS
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <DHT.h>
#endif

#include "LoRaWan_APP.h"

constexpr int PIN_BMP280_SDA = 41;
constexpr int PIN_BMP280_SCL = 42;
constexpr int PIN_DHT11_DATA = 19;
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
constexpr char ID_BALAO[] = "1";

// true  = dados simulados
// false = sensores reais
constexpr bool MODO_SIMULACAO = false;

#define TX_OUTPUT_POWER                             5        // dBm

#define LORA_BANDWIDTH                              0         // [0: 125 kHz,
                                                              //  1: 250 kHz,
                                                              //  2: 500 kHz,
                                                              //  3: Reserved]
#define LORA_SPREADING_FACTOR                       7         // [SF7..SF12]
#define LORA_CODINGRATE                             1         // [1: 4/5,
                                                              //  2: 4/6,
                                                              //  3: 4/7,
                                                              //  4: 4/8]
#define LORA_PREAMBLE_LENGTH                        8         // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT                         0         // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_IQ_INVERSION_ON                        false


#define RX_TIMEOUT_VALUE                            1000
#define BUFFER_SIZE                                 50 // Define the payload size here

char txpacket[BUFFER_SIZE];

double txNumber;

bool lora_idle=true;

static RadioEvents_t RadioEvents;
void OnTxDone( void );
void OnTxTimeout( void );


struct DadosMeteorologicos {
  float temperatura; // Celsius
  float umidade;     // %
  float pressao;     // hPa
  float altitude;    // metros
  float bateria;
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

  return 4.9f;
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
                  String(dados.bateria, 2) + "\n";
  if (lora_idle) {
    delay(1000);
		txNumber += 0.01;
    memcpy(txpacket, pacote.c_str(), pacote.length());
		Radio.Send( (uint8_t *)txpacket, pacote.length() ); //send the package out	
    lora_idle = false;
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

  Mcu.begin(HELTEC_BOARD,SLOW_CLK_TPYE);

  txNumber=0;

  RadioEvents.TxDone = OnTxDone;
  RadioEvents.TxTimeout = OnTxTimeout;
  
  Radio.Init( &RadioEvents );
  Radio.SetChannel( FREQUENCIA_LORA );
  Radio.SetTxConfig( MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                                LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                                LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
                                true, 0, 0, LORA_IQ_INVERSION_ON, 3000 ); 

  if (MODO_SIMULACAO) {
    Serial.println("[INFO] Modo simulacao ativo.");
  } else {
    Serial.println("[INFO] Modo sensores reais ativo.");
  }

  // Permite primeira transmissão imediata
  ultimaTentativa = millis() - INTERVALO_MS;
}

void loop() {
  Radio.IrqProcess();
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

void OnTxDone( void )
{
	Serial.println("TX done......");
	lora_idle = true;
}

void OnTxTimeout( void )
{
    Radio.Sleep( );
    Serial.println("TX Timeout......");
    lora_idle = true;
}
