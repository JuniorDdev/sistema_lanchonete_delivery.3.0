from datetime import datetime
from database import db


class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200))
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    categoria = db.Column(db.String(50))
    estoque = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, default=True)
    imagem_url = db.Column(db.String(255))

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao,
            "preco": float(self.preco),
            "categoria": self.categoria,
            "estoque": self.estoque,
            "ativo": self.ativo,
            "imagem_url": self.imagem_url,
        }


class Pedido(db.Model):
    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.String(20), unique=True, nullable=False)
    cliente_nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    taxa_entrega = db.Column(db.Numeric(10, 2), nullable=False, default=5.00)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=False)
    troco_para = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20), default="novo")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    itens = db.relationship(
        "ItemPedido",
        backref="pedido",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero_pedido,
            "cliente_nome": self.cliente_nome,
            "telefone": self.telefone,
            "endereco": self.endereco,
            "subtotal": float(self.subtotal),
            "taxa_entrega": float(self.taxa_entrega),
            "valor_total": float(self.valor_total),
            "forma_pagamento": self.forma_pagamento,
            "troco_para": float(self.troco_para) if self.troco_para else None,
            "status": self.status,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
            "itens": [item.to_dict() for item in self.itens],
        }


class ItemPedido(db.Model):
    __tablename__ = "itens_pedido"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    produto_nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    observacoes = db.Column(db.Text)

    def to_dict(self):
        return {
            "produto_id": self.produto_id,
            "produto_nome": self.produto_nome,
            "quantidade": self.quantidade,
            "preco_unitario": float(self.preco_unitario),
            "subtotal": float(self.preco_unitario * self.quantidade),
            "observacoes": self.observacoes,
        }


class Funcionario(db.Model):
    __tablename__ = "funcionarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), default="funcionario")
    ativo = db.Column(db.Boolean, default=True)


class Configuracao(db.Model):
    __tablename__ = "configuracoes"

    chave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.String(200))

    @classmethod
    def get(cls, chave, default=None):
        config = cls.query.get(chave)
        return config.valor if config else default

