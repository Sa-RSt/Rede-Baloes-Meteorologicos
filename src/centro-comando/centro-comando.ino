
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <LoRa.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

// 1. CONFIGURAÇÕES DO WIFI
const char* WIFI_SSID = "NOME_DO_WIFI";
const char* WIFI_SENHA = "SENHA_DO_WIFI";

// 2. CONFIGURAÇÕES DA NUVEM
// ThingSpeak
const char* THINGSPEAK_WRITE_KEY = "SUA_WRITE_API_KEY";

const char* THINGSPEAK_URL = "https://api.thingspeak.com/update";

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
const char* ID_BALAO_ESPERADO = "BALAO01";

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

// 6. INICIALIZAÇÃO DO LORA
void iniciarLoRa() {
  SPI.begin(
    PIN_SCK,
    PIN_MISO,
    PIN_MOSI,
    PIN_NSS
  );

  LoRa.setPins(
    PIN_NSS,
    PIN_RST,
    PIN_DIO0
  );

  if (!LoRa.begin(FREQUENCIA_LORA)) {

    Serial.println("[ERRO] Falha ao iniciar LoRa!");

    while (true) {
      delay(1000);
    }
  }

  // Mesmos parâmetros utilizados no balão
  LoRa.setSpreadingFactor(9);
  LoRa.setSignalBandwidth(125000);
  LoRa.setCodingRate4(5);
  LoRa.setSyncWord(0x12);
  LoRa.enableCrc();

  Serial.println("[OK] LoRa inicializado!");
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

  Serial.print("[LoRa] Recebido: ");
  Serial.println(pacote);

  DadosMeteorologicos dados = {};

  if (!interpretarPacote(pacote, dados)) {

    Serial.println("[ERRO] Pacote invalido.");
    return;
  }

  // Qualidade do sinal recebido
  dados.rssi = LoRa.packetRssi();
  dados.snr = LoRa.packetSnr();

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

  WiFiClientSecure cliente;

  // SOMENTE PARA PROTOTIPAGEM:
  // HTTPS sem validação do certificado.
  // Substituir por validação TLS em produção.
  cliente.setInsecure();

  HTTPClient http;

  if (!http.begin(cliente, THINGSPEAK_URL)) {

    Serial.println("[Nuvem] Falha ao iniciar HTTPS.");
    return false;
  }

  http.setTimeout(8000);

  http.addHeader(
    "Content-Type",
    "application/x-www-form-urlencoded"
  );

  // Monta o corpo HTTP com os 8 campos
  String corpo = "api_key=";
  corpo += THINGSPEAK_WRITE_KEY;

  corpo += "&field1=" + String(dados.temperatura, 2);
  corpo += "&field2=" + String(dados.umidade, 2);
  corpo += "&field3=" + String(dados.pressao, 2);
  corpo += "&field4=" + String(dados.altitude, 2);
  corpo += "&field5=" + String(dados.bateria, 2);
  corpo += "&field6=" + String(dados.rssi);
  corpo += "&field7=" + String(dados.snr, 2);
  corpo += "&field8=" + String(dados.sequencia);

  corpo += "&status=" + String(dados.id);

  Serial.println("[Nuvem] Enviando leitura...");

  int codigoHTTP = http.POST(corpo);

  String resposta = "";

  if (codigoHTTP > 0) {
    resposta = http.getString();
    resposta.trim();
  }

  http.end();

  // ThingSpeak retorna o ID da entrada
  // ou "0" em caso de falha de gravacao.
  if (codigoHTTP == 200 &&
      resposta.length() > 0 &&
      resposta != "0") {

    Serial.print("[Nuvem] Leitura gravada! ID=");
    Serial.println(resposta);

    return true;
  }

  Serial.printf(
    "[Nuvem] Falha. HTTP=%d Resposta=%s\n",
    codigoHTTP,
    resposta.c_str()
  );

  return false;
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

  iniciarLoRa();
  iniciarWiFi();

  Serial.println("[Sistema] Central inicializada.");
  Serial.println("[Sistema] Aguardando pacotes...");
}

void loop() {
  // Mantem a conexao Wi-Fi
  verificarWiFi();

  // Recebe e interpreta mensagens LoRa
  receberDadosLoRa();

  // Envia leituras pendentes para a nuvem
  processarEnvioNuvem();

  delay(10);
}
