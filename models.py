from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    contato = db.Column(db.String(20), unique=True, nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    estagio = db.Column(db.String(20), default="NOVO")
    status_comercial = db.Column(db.String(30), default="NOVO")
    acao_pendente = db.Column(db.String(50))
    comentario = db.Column(db.Text)
    motivo_sem_interesse = db.Column(db.String(50))

    interacoes = db.relationship(
        "Historico", backref="lead", lazy=True, order_by="desc(Historico.data)"
    )


class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=False)
    acao = db.Column(db.String(50))
    mensagem = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.now)
