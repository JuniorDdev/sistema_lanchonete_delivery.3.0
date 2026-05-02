from datetime import datetime, timedelta
from functools import wraps
import logging
import os

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from models import Configuracao, Funcionario, ItemPedido, Pedido, Produto


app = Flask(__name__, instance_relative_config=True)
CORS(app)

os.makedirs(app.instance_path, exist_ok=True)
os.makedirs("logs", exist_ok=True)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "mude-essa-chave-em-producao")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "lanchonete.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

logging.basicConfig(
    filename="logs/sistema.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def login_obrigatorio(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def requer_dono(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("usuario_tipo") != "dono":
            return jsonify({"erro": "Acesso negado"}), 403
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def index():
    taxa_entrega = float(Configuracao.get("taxa_entrega_fixa", "5.00"))
    return render_template("index.html", taxa_entrega=taxa_entrega)


@app.route("/admin")
def admin():
    """Atalho para a área administrativa."""
    return redirect(url_for("admin_login"))


@app.route("/api/produtos")
def api_produtos():
    produtos = Produto.query.filter_by(ativo=True).order_by(Produto.categoria, Produto.nome).all()
    return jsonify([p.to_dict() for p in produtos])


@app.route("/checkout")
def checkout():
    taxa_entrega = float(Configuracao.get("taxa_entrega_fixa", "5.00"))
    return render_template("checkout.html", taxa_entrega=taxa_entrega)


@app.route("/api/pedidos", methods=["POST"])
def criar_pedido():
    dados = request.get_json(silent=True) or {}

    campos = ["cliente_nome", "endereco", "itens", "subtotal", "taxa_entrega", "total", "forma_pagamento"]
    if any(c not in dados for c in campos):
        return jsonify({"erro": "Dados incompletos para criar pedido."}), 400

    try:
        ultimo_pedido = Pedido.query.order_by(Pedido.id.desc()).first()
        novo_numero = f"{(ultimo_pedido.id + 1) if ultimo_pedido else 1:04d}"

        pedido = Pedido(
            numero_pedido=novo_numero,
            cliente_nome=dados["cliente_nome"],
            telefone=dados.get("telefone", ""),
            endereco=dados["endereco"],
            subtotal=dados["subtotal"],
            taxa_entrega=dados["taxa_entrega"],
            valor_total=dados["total"],
            forma_pagamento=dados["forma_pagamento"],
            troco_para=dados.get("troco_para"),
            status="novo",
        )

        for item in dados["itens"]:
            produto = Produto.query.get(item["produto_id"])

            if not produto or not produto.ativo:
                db.session.rollback()
                return jsonify({"erro": "Produto não encontrado ou indisponível."}), 400

            quantidade = int(item["quantidade"])
            if quantidade <= 0:
                db.session.rollback()
                return jsonify({"erro": "Quantidade inválida."}), 400

            if produto.estoque < quantidade:
                db.session.rollback()
                return jsonify({"erro": f"Estoque insuficiente para {produto.nome}. Disponível: {produto.estoque}"}), 400

            produto.estoque -= quantidade
            item_pedido = ItemPedido(
                produto_id=produto.id,
                produto_nome=produto.nome,
                quantidade=quantidade,
                preco_unitario=produto.preco,
                observacoes=item.get("observacoes", ""),
            )
            pedido.itens.append(item_pedido)

        db.session.add(pedido)
        db.session.commit()

        return jsonify({
            "sucesso": True,
            "pedido_id": pedido.id,
            "numero_pedido": pedido.numero_pedido,
        }), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar pedido: {e}", exc_info=True)
        return jsonify({"erro": "Falha ao processar pedido. Tente novamente."}), 500


@app.route("/obrigado/<int:pedido_id>")
def obrigado(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template("obrigado.html", pedido=pedido)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        funcionario = Funcionario.query.filter_by(email=email, ativo=True).first()

        if funcionario and check_password_hash(funcionario.senha_hash, senha):
            session["usuario_id"] = funcionario.id
            session["usuario_nome"] = funcionario.nome
            session["usuario_tipo"] = funcionario.tipo
            return redirect(url_for("admin_dashboard"))

        return render_template("admin_login.html", erro="E-mail ou senha inválidos")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@login_obrigatorio
def admin_dashboard():
    return render_template("admin_dashboard.html")


@app.route("/api/admin/pedidos")
@login_obrigatorio
def api_listar_pedidos():
    pedidos = Pedido.query.order_by(Pedido.created_at.desc()).all()
    return jsonify([p.to_dict() for p in pedidos])


@app.route("/api/admin/pedidos/<int:pedido_id>/status", methods=["PUT"])
@login_obrigatorio
def api_mudar_status(pedido_id):
    dados = request.get_json(silent=True) or {}
    novo_status = dados.get("status")
    status_validos = {"novo", "preparo", "saida", "entregue", "cancelado"}

    if novo_status not in status_validos:
        return jsonify({"erro": "Status inválido."}), 400

    pedido = Pedido.query.get_or_404(pedido_id)
    status_anterior = pedido.status

    try:
        if novo_status == "cancelado" and status_anterior not in ["entregue", "cancelado"]:
            for item in pedido.itens:
                produto = Produto.query.get(item.produto_id)
                if produto:
                    produto.estoque += item.quantidade

        pedido.status = novo_status
        db.session.commit()
        return jsonify({"sucesso": True, "status": novo_status})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao mudar status do pedido {pedido_id}: {e}", exc_info=True)
        return jsonify({"erro": "Erro ao alterar status."}), 500


@app.route("/admin/produtos")
@login_obrigatorio
@requer_dono
def admin_produtos():
    produtos = Produto.query.order_by(Produto.categoria, Produto.nome).all()
    return render_template("admin_produtos.html", produtos=produtos)


@app.route("/api/admin/produtos", methods=["POST"])
@login_obrigatorio
@requer_dono
def api_criar_produto():
    dados = request.get_json(silent=True) or {}

    try:
        produto = Produto(
            nome=dados["nome"],
            descricao=dados.get("descricao", ""),
            preco=dados["preco"],
            categoria=dados.get("categoria", ""),
            estoque=int(dados.get("estoque", 0)),
            imagem_url=dados.get("imagem_url", ""),
            ativo=bool(dados.get("ativo", True)),
        )
        db.session.add(produto)
        db.session.commit()
        return jsonify(produto.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar produto: {e}", exc_info=True)
        return jsonify({"erro": "Erro ao criar produto."}), 500


@app.route("/api/admin/produtos/<int:produto_id>", methods=["PUT"])
@login_obrigatorio
@requer_dono
def api_editar_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    dados = request.get_json(silent=True) or {}

    produto.nome = dados.get("nome", produto.nome)
    produto.descricao = dados.get("descricao", produto.descricao)
    produto.preco = dados.get("preco", produto.preco)
    produto.categoria = dados.get("categoria", produto.categoria)
    produto.estoque = int(dados.get("estoque", produto.estoque))
    produto.imagem_url = dados.get("imagem_url", produto.imagem_url)
    produto.ativo = bool(dados.get("ativo", produto.ativo))

    db.session.commit()
    return jsonify(produto.to_dict())


@app.route("/api/admin/produtos/<int:produto_id>", methods=["DELETE"])
@login_obrigatorio
@requer_dono
def api_deletar_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    produto.ativo = False
    db.session.commit()
    return jsonify({"sucesso": True})


@app.route("/admin/relatorios")
@login_obrigatorio
def admin_relatorios():
    return render_template("admin_relatorios.html")


@app.route("/api/admin/relatorios/faturamento")
@login_obrigatorio
def api_faturamento():
    hoje = datetime.utcnow().date()
    inicio_mes = datetime(hoje.year, hoje.month, 1)

    pedidos_hoje = Pedido.query.filter(
        func.date(Pedido.created_at) == hoje,
        Pedido.status == "entregue",
    ).all()
    faturamento_hoje = sum(float(p.valor_total) for p in pedidos_hoje)

    pedidos_mes = Pedido.query.filter(
        Pedido.created_at >= inicio_mes,
        Pedido.status == "entregue",
    ).all()
    faturamento_mes = sum(float(p.valor_total) for p in pedidos_mes)

    total_pedidos_hoje = Pedido.query.filter(func.date(Pedido.created_at) == hoje).count()
    ticket_medio = faturamento_hoje / len(pedidos_hoje) if pedidos_hoje else 0

    produtos_mais_vendidos = db.session.query(
        ItemPedido.produto_nome,
        func.sum(ItemPedido.quantidade).label("total_vendido"),
    ).join(Pedido).filter(
        Pedido.status == "entregue",
        func.date(Pedido.created_at) >= (hoje - timedelta(days=30)),
    ).group_by(ItemPedido.produto_nome).order_by(func.sum(ItemPedido.quantidade).desc()).limit(5).all()

    por_status = db.session.query(Pedido.status, func.count(Pedido.id)).group_by(Pedido.status).all()

    return jsonify({
        "faturamento_hoje": faturamento_hoje,
        "faturamento_mes": faturamento_mes,
        "total_pedidos_hoje": total_pedidos_hoje,
        "ticket_medio": ticket_medio,
        "produtos_mais_vendidos": [{"nome": p[0], "total": int(p[1])} for p in produtos_mais_vendidos],
        "por_status": [{"status": s, "total": int(t)} for s, t in por_status],
    })


def criar_usuario_admin():
    admin = Funcionario.query.filter_by(email="admin@lanchonete.com").first()
    if not admin:
        admin = Funcionario(
            nome="Administrador",
            email="admin@lanchonete.com",
            senha_hash=generate_password_hash("admin123"),
            tipo="dono",
            ativo=True,
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado: admin@lanchonete.com / senha: admin123")


def criar_configuracoes_padrao():
    configs = {
        "taxa_entrega_fixa": ("5.00", "Valor padrão da taxa de entrega"),
    }

    for chave, (valor, descricao) in configs.items():
        if not Configuracao.get(chave):
            db.session.add(Configuracao(chave=chave, valor=valor, descricao=descricao))

    db.session.commit()


def criar_produtos_exemplo():
    if Produto.query.count() == 0:
        produtos = [
            Produto(nome="X-Burger", descricao="Pão, hambúrguer, queijo, alface e tomate", preco=18.00, categoria="Lanches", estoque=50),
            Produto(nome="X-Bacon", descricao="Pão, hambúrguer, queijo, bacon, alface e tomate", preco=22.00, categoria="Lanches", estoque=50),
            Produto(nome="Batata Frita", descricao="Batata crocante", preco=12.00, categoria="Acompanhamentos", estoque=100),
            Produto(nome="Coca-Cola 2L", descricao="Refrigerante", preco=10.00, categoria="Bebidas", estoque=30),
            Produto(nome="Suco Natural", descricao="Laranja ou limão", preco=8.00, categoria="Bebidas", estoque=40),
        ]
        db.session.add_all(produtos)
        db.session.commit()
        print("Produtos de exemplo criados")


def inicializar_banco():
    with app.app_context():
        db.create_all()
        criar_usuario_admin()
        criar_configuracoes_padrao()
        criar_produtos_exemplo()


if __name__ == "__main__":
    inicializar_banco()
    print("=" * 50)
    print("SERVIDOR INICIADO")
    print("Cliente: http://localhost:5000/")
    print("Admin:   http://localhost:5000/admin/login")
    print("Usuário: admin@lanchonete.com")
    print("Senha:   admin123")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000)
