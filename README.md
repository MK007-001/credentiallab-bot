# CredentialLab 2.0

Bot Telegram para geração de dados sintéticos destinados a desenvolvimento e testes autorizados.

## Recursos
- Menu interativo em português.
- E-mails sintéticos em domínios reservados (`example.com`, `example.org`, `example.net`, `example.test`).
- Senhas aleatórias independentes para ambientes de teste.
- Exportação TXT e CSV.
- Histórico SQLite por usuário.
- Limites básicos de geração.

O bot não cria caixas postais reais, não verifica se endereços existem e não transforma senhas existentes em listas de tentativas.

## Teste local
1. Python 3.10+.
2. `pip install -r requirements.txt`
3. Defina `TELEGRAM_BOT_TOKEN`.
4. `python bot.py`

## Render
Crie um **Web Service** conectado ao repositório GitHub:
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`

Variáveis de ambiente:
- `TELEGRAM_BOT_TOKEN`: token do BotFather
- `WEBHOOK_SECRET`: string aleatória com letras, números, `_` ou `-` (1 a 256 caracteres)
- `WEBHOOK_PATH`: opcional; por padrão `credentiallab-webhook`

O Render define `PORT` e `RENDER_EXTERNAL_URL` automaticamente.

Observação: o serviço gratuito do Render pode suspender-se por inatividade e não garante operação contínua 24/7. SQLite no disco efêmero pode ser perdido em reinicializações/deploys; use disco persistente ou banco externo se o histórico precisar sobreviver.
