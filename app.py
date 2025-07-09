from flask import Flask, request, render_template, send_file, redirect, url_for
from docxtpl import DocxTemplate
from docx import Document
import tempfile, platform, subprocess, os, sqlite3, uuid
from datetime import datetime

app = Flask(__name__, static_url_path='', static_folder='portal', template_folder='templates')
ADMIN_PASSWORD = "minha_senha_super_secreta"  # Troque por algo forte

# Banco SQLite
def init_db():
    with sqlite3.connect("chaves.db") as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS chaves_pagamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'ativa',
            cliente TEXT,
            data_uso TIMESTAMP
        )
        """)

def verificar_e_consumir_chave(chave):
    with sqlite3.connect("chaves.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM chaves_pagamento WHERE chave = ?", (chave,))
        row = cur.fetchone()
        if not row:
            return False, "Chave inválida"
        if row[0] != "ativa":
            return False, "Chave já usada ou expirada"
        cur.execute("UPDATE chaves_pagamento SET status='usada', data_uso=? WHERE chave=?", (datetime.now(), chave))
        conn.commit()
        return True, "Chave válida"

def gerar_chaves(qtd, cliente=None):
    chaves = []
    with sqlite3.connect("chaves.db") as conn:
        cur = conn.cursor()
        for _ in range(qtd):
            chave = uuid.uuid4().hex[:10].upper()
            cur.execute("INSERT INTO chaves_pagamento (chave, cliente) VALUES (?, ?)", (chave, cliente))
            chaves.append(chave)
        conn.commit()
    return chaves

def upper(text):
    return text.upper() if text else ""

def format_moeda(valor):
    return f"{valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def remover_paragrafos_vazios_ou_quase_vazios(doc_path):
    doc = Document(doc_path)
    for para in list(doc.paragraphs):
        if not para.text.strip():
            para._element.getparent().remove(para._element)
    doc.save(doc_path)

def converter_para_pdf(docx_path, pdf_path):
    sistema = platform.system()
    if sistema in ["Windows", "Darwin"]:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
    elif sistema == "Linux":
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", docx_path, "--outdir", os.path.dirname(pdf_path)], check=True)

# Página inicial do portal
@app.route("/")
def portal_index():
    return app.send_static_file("index.html")

# Formulário e geração de nota fiscal
@app.route("/notafiscal", methods=["GET", "POST"])
def notafiscal():
    if request.method == "POST":
        chave = request.form.get("chave_pagamento")
        ok, msg = verificar_e_consumir_chave(chave)
        if not ok:
            return f'''
    <div style="text-align: center; font-family: Arial, sans-serif; margin-top: 50px;">
        <h2 style="color: red;">{msg}</h2>
        <button onclick="window.history.back()" style="padding: 10px 20px; font-size: 16px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
            Tentar novamente
        </button>
        <p style="margin-top: 20px;">Obtenha a chave de pagamento contatando o WhatsApp: <a href="https://wa.me/5511999263484" target="_blank">+55 11 99926-3484</a></p>
    </div>
''', 403

        nome = upper(request.form.get("nome"))
        data_compra = request.form.get("data_compra")
        cep = upper(request.form.get("cep"))
        endereco = upper(request.form.get("endereco"))
        numero = upper(request.form.get("numero"))
        complemento = upper(request.form.get("complemento"))
        bairro = upper(request.form.get("bairro"))
        municioio = upper(request.form.get("municioio"))
        uf = upper(request.form.get("uf"))

        itens, valor_total, quantidade_total = [], 0.0, 0
        for i in range(30):
            nome_item = upper(request.form.get(f"item_nome_{i}"))
            qtd = request.form.get(f"item_qtd_{i}")
            unit = request.form.get(f"item_unit_{i}")
            if nome_item and qtd and unit:
                qtd, unit = int(qtd), float(unit)
                total = qtd * unit
                valor_total += total
                quantidade_total += qtd
                itens.append({"nome": nome_item, "qtd": qtd, "unitario": format_moeda(unit), "total": format_moeda(total)})

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "saida.docx")
            pdf_path = os.path.join(tmpdir, "saida.pdf")
            doc = DocxTemplate("nota_template.docx")
            context = {
                "nome": nome, "data_compra": data_compra, "cep": cep, "endereco": endereco, "numero": numero,
                "complemento": complemento, "bairro": bairro, "municioio": municioio, "uf": uf,
                "itens": itens, "valor_total": format_moeda(valor_total), "quantidade_total": quantidade_total
            }
            doc.render(context)
            doc.save(docx_path)
            remover_paragrafos_vazios_ou_quase_vazios(docx_path)
            converter_para_pdf(docx_path, pdf_path)
            return send_file(pdf_path, as_attachment=True, download_name=f"{nome}_nota.pdf")

    return render_template("form.html")

# Administração de chaves
@app.route("/admin", methods=["GET", "POST"])
def admin():
    senha = request.args.get("senha")
    if senha != ADMIN_PASSWORD:
        return "<h2 style='color:red;'>Acesso não autorizado.</h2>", 403

    if request.method == "POST":
        qtd = int(request.form.get("quantidade"))
        cliente = request.form.get("cliente")
        gerar_chaves(qtd, cliente)

    with sqlite3.connect("chaves.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT chave, cliente FROM chaves_pagamento WHERE status = 'ativa'")
        chaves = cur.fetchall()

    return render_template("admin.html", chaves=chaves)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
