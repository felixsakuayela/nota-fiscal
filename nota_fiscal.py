from flask import Flask, render_template_string, request, send_file
from docxtpl import DocxTemplate
from docx import Document
import platform
import tempfile
import subprocess
import os

app = Flask(__name__)

def upper(text):
    return text.upper() if text else ""

def format_moeda(valor):
    return f"{valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def remover_paragrafos_vazios_ou_quase_vazios(doc_path):
    doc = Document(doc_path)
    paras_a_remover = []
    for para in doc.paragraphs:
        texto = para.text
        if texto is None or texto.strip() == "":
            paras_a_remover.append(para)
    for para in paras_a_remover:
        p = para._element
        p.getparent().remove(p)
    doc.save(doc_path)

HTML_FORM = '''
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>Gerador de Nota Fiscal</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 900px;
      margin: 2rem auto;
      background: #f9f9f9;
      padding: 2rem;
      border-radius: 8px;
      box-shadow: 0 0 15px rgba(0,0,0,0.1);
    }
    h2 {
      color: #333;
      border-bottom: 2px solid #ccc;
      padding-bottom: 5px;
    }
    label {
      display: block;
      margin-top: 10px;
      font-weight: bold;
    }
    input[type="text"], input[type="date"], input[type="number"] {
      padding: 6px;
      margin-top: 4px;
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #ccc;
      border-radius: 4px;
    }
    table {
      width: 100%;
      margin-top: 1em;
      border-collapse: collapse;
    }
    th, td {
      border: 1px solid #aaa;
      padding: 8px;
      text-align: left;
    }
    th {
      background-color: #eee;
    }
    .item-total {
      font-weight: bold;
    }
    button, input[type="submit"] {
      background-color: #28a745;
      color: white;
      border: none;
      padding: 10px 20px;
      margin-top: 15px;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
    }
    button:hover, input[type="submit"]:hover {
      background-color: #218838;
    }
  </style>
</head>
<body>
<h1 style="color: #218838;">Emissor de Nota Fiscal</h1>
<h2>Informações do Cliente</h2>
<form method="post">
  <label>Nome do Cliente:</label>
  <input type="text" name="nome" required>

  <label>Data da Compra:</label>
  <input type="date" name="data_compra" required>

  <label>CEP:</label>
  <input type="text" name="cep" id="cep" required onblur="buscarCEP()">

  <label>Endereço:</label>
  <input type="text" name="endereco" id="endereco" required>

  <label>Número:</label>
  <input type="text" name="numero" required>

  <label>Complemento:</label>
  <input type="text" name="complemento">

  <label>Bairro:</label>
  <input type="text" name="bairro" id="bairro" required>

  <label>Município:</label>
  <input type="text" name="municioio" id="municioio" required>

  <label>UF:</label>
  <input type="text" name="uf" id="uf" required>

  <h2>Itens da Nota Fiscal</h2>
  <table id="itens-tabela">
    <thead>
      <tr>
        <th>Nome do Item</th>
        <th>Quantidade</th>
        <th>Valor Unitário (R$)</th>
        <th>Valor Total (R$)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><input type="text" name="item_nome_0" required></td>
        <td><input type="number" name="item_qtd_0" min="1" value="1" oninput="atualizarTotal(this)"></td>
        <td><input type="number" step="0.01" name="item_unit_0" value="0.00" oninput="atualizarTotal(this)"></td>
        <td class="item-total">R$ 0,00</td>
      </tr>
    </tbody>
  </table>

  <button type="button" onclick="adicionarItem()">+ Adicionar Item</button>

  <h3>Total da Nota: <span id="valor-total-nota">R$ 0,00</span></h3>
  <h3>Total de Quantidade de Itens: <span id="total-quantidade">0</span></h3>

  <input type="submit" value="Gerar NOTA FISCAL">
  <h5> Mais informações contate whatsapp: <a href="https://wa.me/5511999263484" target="_blank">+55 11 99926-3484</a></h5>
</form>

<script>
  let contador = 1;

  function formatarMoeda(valor) {
    return "R$ " + valor.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function atualizarTotal(input) {
    const linha = input.closest("tr");
    const qtd = parseFloat(linha.querySelector('input[name^="item_qtd_"]').value) || 0;
    const unit = parseFloat(linha.querySelector('input[name^="item_unit_"]').value) || 0;
    const total = qtd * unit;
    linha.querySelector(".item-total").innerText = formatarMoeda(total);
    atualizarTotais();
  }

  function atualizarTotais() {
    let totalNota = 0;
    let totalQtd = 0;
    document.querySelectorAll("tbody tr").forEach(linha => {
      const qtd = parseInt(linha.querySelector('input[name^="item_qtd_"]').value) || 0;
      const unit = parseFloat(linha.querySelector('input[name^="item_unit_"]').value) || 0;
      totalNota += qtd * unit;
      totalQtd += qtd;
    });
    document.getElementById("valor-total-nota").innerText = formatarMoeda(totalNota);
    document.getElementById("total-quantidade").innerText = totalQtd;
  }

  function buscarCEP() {
    const cep = document.getElementById("cep").value.replace(/\D/g, '');
    if (cep.length !== 8) return;
    fetch(`https://viacep.com.br/ws/${cep}/json/`)
      .then(response => response.json())
      .then(data => {
        if (data.erro) {
          alert("CEP não encontrado.");
          return;
        }
        document.getElementById("endereco").value = data.logradouro.toUpperCase();
        document.getElementById("bairro").value = data.bairro.toUpperCase();
        document.getElementById("municioio").value = data.localidade.toUpperCase();
        document.getElementById("uf").value = data.uf.toUpperCase();
      })
      .catch(() => alert("Erro ao consultar o CEP."));
  }

  function adicionarItem() {
    if (contador >= 30) {
      alert("Limite de 30 itens atingido.");
      return;
    }
    const tbody = document.querySelector("#itens-tabela tbody");
    const novaLinha = document.createElement("tr");
    novaLinha.innerHTML = `
      <td><input type="text" name="item_nome_${contador}" required></td>
      <td><input type="number" name="item_qtd_${contador}" min="1" value="1" oninput="atualizarTotal(this)"></td>
      <td><input type="number" step="0.01" name="item_unit_${contador}" value="0.00" oninput="atualizarTotal(this)"></td>
      <td class="item-total">R$ 0,00</td>
    `;
    tbody.appendChild(novaLinha);
    contador++;
  }

  window.onload = atualizarTotais;
</script>

</body>
</html>
'''

def converter_para_pdf(docx_path, pdf_path):
    sistema = platform.system()
    if sistema in ["Windows", "Darwin"]:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
    elif sistema == "Linux":
        subprocess.run([
            "libreoffice", "--headless", "--convert-to", "pdf", docx_path,
            "--outdir", os.path.dirname(pdf_path)
        ], check=True)
    else:
        raise RuntimeError(f"Sistema operacional não suportado: {sistema}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        nome = upper(request.form.get("nome"))
        data_compra = request.form.get("data_compra")
        cep = upper(request.form.get("cep"))
        endereco = upper(request.form.get("endereco"))
        numero = upper(request.form.get("numero"))
        complemento = upper(request.form.get("complemento"))
        bairro = upper(request.form.get("bairro"))
        municioio = upper(request.form.get("municioio"))
        uf = upper(request.form.get("uf"))

        itens = []
        valor_total = 0.0
        quantidade_total = 0

        for i in range(30):
            nome_item = upper(request.form.get(f"item_nome_{i}"))
            qtd = request.form.get(f"item_qtd_{i}")
            unit = request.form.get(f"item_unit_{i}")
            if nome_item and qtd and unit:
                qtd = int(qtd)
                unit = float(unit)
                total = qtd * unit
                valor_total += total
                quantidade_total += qtd
                itens.append({
                    "nome": nome_item,
                    "qtd": qtd,
                    "unitario": format_moeda(unit),
                    "total": format_moeda(total)
                })

        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "saida.docx")
            pdf_path = os.path.join(tmpdir, "saida.pdf")
            doc = DocxTemplate("nota_template.docx")
            context = {
                "nome": nome,
                "data_compra": data_compra,
                "cep": cep,
                "endereco": endereco,
                "numero": numero,
                "complemento": complemento,
                "bairro": bairro,
                "municioio": municioio,
                "uf": uf,
                "itens": itens,
                "valor_total": format_moeda(valor_total),
                "quantidade_total": quantidade_total
            }
            doc.render(context)
            doc.save(docx_path)
            remover_paragrafos_vazios_ou_quase_vazios(docx_path)
            converter_para_pdf(docx_path, pdf_path)
            return send_file(pdf_path, as_attachment=True, download_name=f"{nome}_nota.pdf")

    return render_template_string(HTML_FORM)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
