# Sistema de Lanchonete Delivery - Flask

## Versão corrigida 2.1

Sistema web para lanchonete com:

- Catálogo de produtos
- Carrinho de compras
- Finalização de pedido
- Controle real de estoque
- Área administrativa com login
- Controle de status do pedido
- Relatórios básicos de faturamento

## Como rodar no Windows

1. Abra a pasta no VS Code.
2. No terminal, crie o ambiente virtual:

```bash
python -m venv venv
```

3. Ative o ambiente virtual:

```bash
venv\Scripts\activate
```

4. Instale as dependências:

```bash
pip install -r requirements.txt
```

5. Rode o sistema:

```bash
python app.py
```

6. Acesse:

- Cliente: http://localhost:5000/
- Admin: http://localhost:5000/admin/login

## Login padrão

- E-mail: admin@lanchonete.com
- Senha: admin123

## Observações

O banco SQLite será criado automaticamente em:

```text
instance/lanchonete.db
```

Esta versão não possui comunicação com API de WhatsApp.

## Correções desta versão

- Projeto reorganizado sem pasta duplicada.
- Criada rota `/admin` para redirecionar ao login administrativo.
- Adicionado botão `Área Administrativa` na página inicial.
- Navbar administrativa corrigida e mais visível.
- Abas administrativas: Dashboard, Cardápio, Relatórios e Loja.
- Removidas dependências desnecessárias de WhatsApp/API externa.

