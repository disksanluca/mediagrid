# Opção gratuita: Oracle Cloud Always Free

Uma máquina virtual Ampere A1 da camada Always Free pode executar o MediaGrid em ARM64.
As regras de gratuidade, a verificação de conta e a disponibilidade variam conforme a
Oracle. Confira o selo **Always Free** antes de criar qualquer recurso. Este roteiro
ainda precisa ser testado numa máquina Oracle real.

1. Crie uma conta Oracle Cloud Free Tier e escolha uma região com disponibilidade de
   Ampere A1. A Oracle pode solicitar um cartão para verificar a conta.
2. Crie uma máquina Ubuntu ARM64 do tipo **Always Free eligible**,
   `VM.Standard.A1.Flex`, com 2 OCPUs, 12 GB de RAM e disco de 50 GB. Ative um IPv4
   público e confira o selo gratuito antes de confirmar.
3. Nas regras de rede da Oracle e no firewall da máquina, libere as portas TCP 22 (SSH),
   80 (HTTP) e 443 (HTTPS). Se possível, restrinja a porta 22 ao seu próprio IP.
4. Instale Docker Engine com o plugin Compose pelo [guia oficial para Ubuntu](https://docs.docker.com/engine/install/ubuntu/).
   Depois, instale o Git e copie o projeto na máquina:

   ```bash
   sudo apt update
   sudo apt install -y git
   git clone https://github.com/disksanluca/mediagrid.git
   cd mediagrid
   ```
5. Você pode usar um endereço DNS gratuito baseado no IP da máquina. Exemplo: para o IP
   `203.0.113.10`, use `MEDIAGRID_DOMAIN=203.0.113.10.sslip.io`. Confira se o endereço
   resolve para o IP da máquina antes de iniciar o Caddy.
6. Na pasta do projeto, execute `cp deploy/.env.example deploy/.env` e edite o novo
   arquivo. Preencha o domínio e três senhas diferentes e longas. Gere valores na
   própria máquina com `openssl rand -hex 32`. Use `nano deploy/.env` para editar e
   salve com Ctrl+O, Enter e Ctrl+X. Não envie as senhas pelo chat.
7. Execute `sudo docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build`.
   A primeira compilação instala o Chromium e pode demorar vários minutos. Verifique
   o estado com `sudo docker compose --env-file deploy/.env -f deploy/compose.yaml ps`.
8. Abra `https://SEU_DOMINIO` no navegador. O Caddy obtém o certificado HTTPS quando
   o DNS e as portas 80/443 chegam à máquina. Entre com `MEDIAGRID_ADMIN_PASSWORD`.

O banco de dados, os vídeos e os certificados ficam em volumes Docker na máquina.
Apagar a máquina ou esses volumes apaga seus dados. Faça backup antes de atualizações.
Se o IP público mudar, atualize o domínio e o arquivo `deploy/.env`.
