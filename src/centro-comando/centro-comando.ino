#include <Arduino.h>
#include <WiFi.h>
#include <SPI.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <MQTTClient.h>
#include <ArduinoJson.h>

// CONFIGURAÇÕES DO WIFI
const char* WIFI_SSID = "Bo dia";
const char* WIFI_SENHA = "euth1347";

const char MQTT_BROKER_ADRRESS[] = "10.99.127.20";
const int MQTT_BROKER_PORT = 1883;
const char MQTT_CLIENT_ID[] = "CENTRO-COMANDO-esp32-001";
const char MQTT_USERNAME[] = "";
const char MQTT_PASSWORD[] = ""; 
const char MQTT_TOPIC[] = "sensores";

// Intervalo entre tentativas de envio
constexpr unsigned long INTERVALO_NUVEM_MS = 20000UL;

// Intervalo de verificação do Wi-Fi
constexpr unsigned long INTERVALO_WIFI_MS = 10000UL;

// 3. CONFIGURAÇÕES DO LORA
constexpr int PIN_SCK  = 18;
constexpr int PIN_MISO = 19;
constexpr int PIN_MOSI = 23;
constexpr int PIN_NSS  = 5;
constexpr int PIN_RST  = 14;
constexpr int PIN_DIO0 = 26;

constexpr long FREQUENCIA_LORA = 915500000L;

// Identificador esperado do balão
const char* ID_BALAO_ESPERADO = "1";

// 4. ESTRUTURA DOS DADOS METEOROLÓGICOS
struct DadosMeteorologicos {
  char id[16];

  unsigned long sequencia;

  float temperatura;
  float umidade;
  float pressao;
  float altitude;
  float bateria;

  int rssi;
  float snr;
};

// Armazena a última leitura ainda não enviada
DadosMeteorologicos ultimaLeitura;

bool leituraPendente = false;
bool jaTentouEnviar = false;
bool wifiConectadoAnteriormente = false;

unsigned long ultimaTentativaNuvem = 0;
unsigned long ultimaTentativaWiFi = 0;

WiFiClient cliente;
MQTTClient mqtt = MQTTClient(256);

// 5. CONEXÃO WIFI
void iniciarWiFi() {
  Serial.println("[WiFi] Iniciando conexao...");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);

  WiFi.begin(WIFI_SSID, WIFI_SENHA);

  ultimaTentativaWiFi = millis();
}

void verificarWiFi() {
  if (WiFi.status() == WL_CONNECTED) {

    if (!wifiConectadoAnteriormente) {

      Serial.println("[WiFi] Conectado!");
      Serial.print("[WiFi] IP: ");
      Serial.println(WiFi.localIP());

      wifiConectadoAnteriormente = true;
    }

    return;
  }

  if (wifiConectadoAnteriormente) {

    Serial.println("[WiFi] Conexao perdida.");
    wifiConectadoAnteriormente = false;
  }

  // Tenta reconectar sem bloquear o loop
  if (millis() - ultimaTentativaWiFi >= INTERVALO_WIFI_MS) {

    Serial.println("[WiFi] Tentando reconectar...");

    WiFi.reconnect();

    ultimaTentativaWiFi = millis();
  }
}

void conectarMQTT() {
  mqtt.begin(MQTT_BROKER_ADRRESS, MQTT_BROKER_PORT, cliente);

  Serial.print("[MQTT] Conectando");

  while (!mqtt.connect(MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
    Serial.print(".");
    delay(100);
  }
  Serial.println();

  if (!mqtt.connected()) {
    Serial.println("[MQTT] Timeout!");
    return;
  }

  // Subscribe to a topic, the incoming messages are processed by messageHandler() function
  if (mqtt.subscribe(MQTT_TOPIC))
    Serial.print("[MQTT] Subscribed: ");
  else
    Serial.print("[MQTT] Failed to subscribe: ");

  Serial.println(MQTT_TOPIC);
}

// 7. INTERPRETAÇÃO DOS DADOS RECEBIDOS
// Formato esperado:
// ID,seq,temperatura,umidade,pressao,altitude,bateria
bool interpretarPacote(
  const String& pacote,
  DadosMeteorologicos& dados
) {
  char caractereExtra;

  int campos = sscanf(
    pacote.c_str(),
    "%15[^,],%lu,%f,%f,%f,%f,%f%c",

    dados.id,
    &dados.sequencia,
    &dados.temperatura,
    &dados.umidade,
    &dados.pressao,
    &dados.altitude,
    &dados.bateria,
    &caractereExtra
  );

  // Exige exatamente 7 campos
  if (campos != 7) {
    return false;
  }

  // Verifica a origem da mensagem
  if (strcmp(dados.id, ID_BALAO_ESPERADO) != 0) {
    return false;
  }

  // Verifica valores inválidos
  if (!isfinite(dados.temperatura) ||
      !isfinite(dados.umidade) ||
      !isfinite(dados.pressao) ||
      !isfinite(dados.altitude) ||
      !isfinite(dados.bateria)) {

    return false;
  }

  // Limites básicos de consistência
  if (dados.temperatura < -100.0f ||
      dados.temperatura > 100.0f ||
      dados.umidade < 0.0f ||
      dados.umidade > 100.0f ||
      dados.pressao < 100.0f ||
      dados.pressao > 1200.0f ||
      dados.altitude < -500.0f ||
      dados.altitude > 60000.0f ||
      dados.bateria < 0.0f ||
      dados.bateria > 5.0f) {

    return false;
  }

  return true;
}

// 8. EXIBIÇÃO DOS DADOS
void mostrarDados(const DadosMeteorologicos& dados) {
  Serial.println();
  Serial.println("================================");
  Serial.println("     LEITURA METEOROLOGICA");
  Serial.println("================================");

  Serial.printf(
    "Balao: %s\n",
    dados.id
  );

  Serial.printf(
    "Mensagem: %lu\n",
    dados.sequencia
  );

  Serial.printf(
    "Temperatura: %.2f C\n",
    dados.temperatura
  );

  Serial.printf(
    "Umidade: %.2f %%\n",
    dados.umidade
  );

  Serial.printf(
    "Pressao: %.2f hPa\n",
    dados.pressao
  );

  Serial.printf(
    "Altitude: %.2f m\n",
    dados.altitude
  );

  Serial.printf(
    "Bateria: %.2f V\n",
    dados.bateria
  );

  Serial.printf(
    "RSSI: %d dBm\n",
    dados.rssi
  );

  Serial.printf(
    "SNR: %.2f dB\n",
    dados.snr
  );

  Serial.println("================================");
}

// 9. RECEPÇÃO VIA LORA
void receberDadosLoRa() {
/*
  int tamanhoPacote = LoRa.parsePacket();

  if (tamanhoPacote == 0) {
    return;
  }

  // Limita o tamanho aceito
  if (tamanhoPacote > 120) {

    while (LoRa.available()) {
      LoRa.read();
    }

    Serial.println("[LoRa] Pacote muito grande.");
    return;
  }

  String pacote;
  pacote.reserve(121);

  while (LoRa.available()) {
    pacote += (char)LoRa.read();
  }
*/
  String pacote = "0,1,27.67,69.420,100000.33,11.11,4.76";
  Serial.print("[LoRa] Recebido: ");
  Serial.println(pacote);

  DadosMeteorologicos dados = {};

  if (!interpretarPacote(pacote, dados)) {

    Serial.println("[ERRO] Pacote invalido.");
    return;
  }

  // Qualidade do sinal recebido
  dados.rssi = -1;  // TODO
  dados.snr = 1;  // TODO

  mostrarDados(dados);

  // Guarda a leitura para envio na nuvem.
  // Se houver outra pendente, a nova substitui a antiga.
  if (leituraPendente) {
    Serial.println(
      "[INFO] Leitura pendente substituida."
    );
  }

  ultimaLeitura = dados;
  leituraPendente = true;
}

// 10. ENVIO PARA O THINGSPEAK
bool enviarParaNuvem(const DadosMeteorologicos& dados) {
  if (WiFi.status() != WL_CONNECTED) {

    Serial.println("[Nuvem] Wi-Fi indisponivel.");
    return false;
  }

  StaticJsonDocument<500> message;
  message["sensores"][0]["nome"] = "Temperatura";
  message["sensores"][0]["leitura"] = dados.temperatura;
  message["sensores"][0]["balao"] = dados.id;
  message["sensores"][1]["nome"] = "Umidade";
  message["sensores"][1]["leitura"] = dados.umidade;
  message["sensores"][1]["balao"] = dados.id;
  message["sensores"][2]["nome"] = "Pressão";
  message["sensores"][2]["leitura"] = dados.pressao;
  message["sensores"][2]["balao"] = dados.id;
  message["sensores"][3]["nome"] = "Altitude";
  message["sensores"][3]["leitura"] = dados.altitude;
  message["sensores"][3]["balao"] = dados.id;
  message["sensores"][4]["nome"] = "Bateria";
  message["sensores"][4]["leitura"] = dados.bateria;
  message["sensores"][4]["balao"] = dados.id;
  char messageBuffer[1024];
  serializeJson(message, messageBuffer);

  mqtt.publish(MQTT_TOPIC, messageBuffer);

  Serial.println("ESP32 - sent to MQTT:");
  Serial.print("- topic: ");
  Serial.println(MQTT_TOPIC);
  Serial.print("- payload:");
  Serial.println(messageBuffer);
}

// 11. CONTROLE DE ENVIO PARA A NUVEM
void processarEnvioNuvem() {
  if (!leituraPendente) {
    return;
  }

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  unsigned long agora = millis();

  // Respeita o intervalo minimo configurado

  if (jaTentouEnviar && agora - ultimaTentativaNuvem < INTERVALO_NUVEM_MS) {

    return;
  }

  ultimaTentativaNuvem = agora;
  jaTentouEnviar = true;

  if (enviarParaNuvem(ultimaLeitura)) {

    leituraPendente = false;

  } else {

    Serial.println(
      "[Nuvem] Leitura mantida para nova tentativa."
    );
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println();
  Serial.println("================================");
  Serial.println(" CENTRAL METEOROLOGICA - ESP32");
  Serial.println("================================");

    // TODO iniciarLoRa();
  iniciarWiFi();

  Serial.println("[Sistema] Central inicializada.");
  Serial.println("[Sistema] Aguardando pacotes...");
}

void loop() {
  mqtt.loop();
  // Mantem a conexao Wi-Fi
  verificarWiFi();

  // Recebe e interpreta mensagens LoRa
  receberDadosLoRa();

  // Envia leituras pendentes para a nuvem
  processarEnvioNuvem();

  delay(10);
}
