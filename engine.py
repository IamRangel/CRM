import pandas as pd
import re
import random
from datetime import datetime

# Palavras que o sistema deve ignorar ao tentar extrair o primeiro nome do cliente
PALAVRAS_IGNORAR = {
    "VISITA",
    "EXP",
    "AGENDAR",
    "-",
    "EX",
    "CONTATO",
    "DUPLICADO",
    "PERSONAL",
    "AVALIAÇÃO",
    "TESTE",
}


def tempo_relativo(dt):
    """Calcula há quanto tempo ocorreu a última interação."""
    if not dt:
        return "Sem registros"
    diff = datetime.now() - dt
    if diff.days > 0:
        return f"há {diff.days}d"
    if diff.seconds >= 3600:
        return f"há {diff.seconds // 3600}h"
    if diff.seconds >= 60:
        return f"há {diff.seconds // 60}m"
    return "agora"


def extrair_primeiro_nome(nome_completo):
    """Limpa o nome do cliente e extrai apenas o primeiro nome válido."""
    if not nome_completo or not isinstance(nome_completo, str):
        return "Cliente"

    # Remove caracteres especiais
    nome_completo = re.sub(r"[^A-Za-zÀ-ÿ\s]", "", nome_completo)
    palavras = nome_completo.upper().split()

    for p in palavras:
        if p in PALAVRAS_IGNORAR:
            continue
        if p.isalpha() and len(p) > 1:
            return p.capitalize()
    return "Cliente"


def definir_estagio(dias):
    """Define a temperatura do lead com base nos dias desde o cadastro."""
    if dias <= 7:
        return "NOVO"
    elif dias <= 14:
        return "EM_CONTATO"
    elif dias <= 21:
        return "MORNO"
    elif dias <= 30:
        return "FRIO"
    return "CONGELADO"


def decidir_acao_lead(lead):
    """
    Decide qual a próxima ação comercial.
    Retorna None se o lead não precisar de mensagem agora.
    """
    # REGRA CRÍTICA: Se estiver sem interesse ou já negociando, não gera pendência
    if lead.status_comercial in ["NEGOCIANDO", "SEM_INTERESSE", "FECHADO"]:
        return None

    # Se for interessado, a prioridade é sempre o Follow-up
    if lead.status_comercial == "INTERESSADO":
        return "FOLLOWUP"

    ultima = lead.interacoes[0] if lead.interacoes else None
    dias_ultima = (datetime.now() - ultima.data).days if ultima else None

    # Se nunca houve contato
    if lead.estagio == "NOVO" and dias_ultima is None:
        return "PRIMEIRO_CONTATO"

    # Se o último contato foi há mais de 5 dias (Reativação)
    if dias_ultima and dias_ultima >= 5:
        return "REATIVACAO"

    return None


def montar_mensagem(nome, acao):
    """Gera uma mensagem aleatória para evitar bloqueios no WhatsApp."""
    phd = "Aqui é da Phd São Braz"

    variacoes = {
        "PRIMEIRO_CONTATO": [
            f"Olá {nome}, tudo bem? Aqui é da PhD São Braz 👋 Vi que você veio conhecer a academia/fez um experimental com a gente. O que você achou da experiência?",
            f"Oi {nome}! Aqui é da PhD São Braz 💪 Vi que você passou por aqui recentemente. Me conta: o que você está buscando hoje com a academia?",
            f"Fala {nome}, tudo certo? Aqui é da PhD São Braz! Recebemos seu cadastro após sua visita. Quero te ajudar a dar o próximo passo — seu foco hoje é mais emagrecimento, ganho de massa ou condicionamento?",
        ],
        "FOLLOWUP": [
            f"{nome}, conseguiu pensar melhor sobre começar os treinos? Posso te ajudar a montar um plano ideal pra sua rotina.",
            f"E aí {nome}! Ficou alguma dúvida sobre valores, planos ou horários? Se quiser, te explico tudo de forma rápida.",
            f"{nome}, bora dar o próximo passo? Posso deixar sua matrícula pronta pra você só vir iniciar 💪",
            f"{nome}, vi que você demonstrou interesse — o que está te impedindo de começar agora? Se precisar, te ajudo nisso.",
        ],
        "REATIVACAO": [
            f"Oi {nome}, tudo bem? Já faz um tempinho desde sua última visita aqui na PhD São Braz 👋 Você ainda tem interesse em começar a treinar?",
            f"{nome}, passando pra te chamar de volta 💪 Muita gente deixa pra depois e acaba adiando o resultado. Bora retomar agora?",
            f"Fala {nome}! Seu plano de começar a treinar ainda está de pé? Posso te ajudar a recomeçar de forma leve e organizada.",
            f"{nome}, estamos com novidades e a academia mudou bastante desde sua última visita. Quer vir conhecer de novo e dar início aos treinos?",
        ],
    }

    lista = variacoes.get(acao, [f"Olá {nome}, tudo bem? {phd}!"])
    return random.choice(lista)


def processar_upload_csv(file_path, db, Lead):
    """Lê o CSV exportado e atualiza/cria os leads no banco de dados."""
    try:
        # Lê o CSV garantindo a codificação correta para nomes com acento
        df = pd.read_csv(file_path, sep=",", encoding="WINDOWS-1252").dropna(
            subset=["Contato", "Cliente"]
        )

        # Converte a data de cadastro
        df["Data cadastro"] = pd.to_datetime(
            df["Data cadastro"], format="mixed", dayfirst=True
        )

        for _, row in df.iterrows():
            contato = str(row["Contato"]).strip()
            # Remove caracteres não numéricos do telefone para evitar duplicados
            contato = re.sub(r"\D", "", contato)

            lead = Lead.query.filter_by(contato=contato).first()
            dias = (datetime.now() - row["Data cadastro"]).days

            if not lead:
                lead = Lead(
                    nome=str(row["Cliente"]),
                    contato=contato,
                    data_cadastro=row["Data cadastro"],
                )
                db.session.add(lead)

            # Atualiza o estágio (Novo, Morno, etc.) com base no tempo de casa
            lead.estagio = definir_estagio(dias)

        db.session.commit()
    except Exception as e:
        print(f"Erro ao processar CSV: {e}")
