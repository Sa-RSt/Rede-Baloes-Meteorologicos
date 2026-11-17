# Como executar o nó do NODE-Red

1. Certifique-se de que o banco de dados SQLite foi criado na interface web.
   Para isso, consulte o arquivo `src/nuvem/interface-web/README.md`.

1. Execute o _broker_ MQTT local: `mosquitto -c mosquitto.conf -v`

1. Abra o NODE-Red **utilizando src/nuvem/interface-web como diretório de trabalho**: `cd src/nuvem/interface-web && node-red`

1. Abra a página local do NODE-Red no navegador e importe o fluxo do arquivo `node-red.json`.

1. Clique em "Deploy".
