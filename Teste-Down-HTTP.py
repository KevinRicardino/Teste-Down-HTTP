import csv
import urllib.request
import urllib.error
import ssl
import os
import threading
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor


# --- FUNÇÕES DE AJUDA PARA O UTILIZADOR ---

def instalar_ferramenta_copiar():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyperclip"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False


try:
    import pyperclip

    pode_copiar = True
except ImportError:
    if instalar_ferramenta_copiar():
        import pyperclip

        pode_copiar = True
    else:
        pode_copiar = False

trava_print = threading.Lock()
contador_processados = 0


def limpar_a_tela():
    if os.name == 'nt':
        os.system('cls')
    else:
        print("\033[H\033[J", end="")


def verificar_se_quer_sair(texto):
    if texto.lower() == 'sair':
        print("\nEncerrando o programa... Ate logo!")
        sys.exit()
    return texto


# --- FUNÇÃO DE VERIFICAÇÃO DE PASTA ---

def verificar_pasta_trabalho():
    caminho_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    pasta_nome = "Teste Down HTTP"
    caminho_completo = os.path.join(caminho_downloads, pasta_nome)

    while True:
        if not os.path.exists(caminho_completo):
            limpar_a_tela()
            print("=" * 65)
            print(f"AVISO: A pasta '{pasta_nome}' nao foi encontrada em Downloads.")
            print("=" * 65)
            print(f"\nPara o programa funcionar, voce precisa:")
            print(f"1. Criar a pasta: {caminho_completo}")
            print(f"2. Colocar o seu arquivo CSV com os links dentro dela.")

            escolha = input("\nRealizar a criacao automatica desta pasta? (s/n): ").strip().lower()
            verificar_se_quer_sair(escolha)

            if escolha == 's':
                os.makedirs(caminho_completo)
                print(f"\n✅ Pasta criada com sucesso!")
                print(f"👉 AGORA, COPIE SEU ARQUIVO CSV PARA: {caminho_completo}")
                input("\nAperte [ENTER] apos colocar o arquivo na pasta para continuar...")
                # Após o enter, o loop volta ao topo e checa o exists() de novo
                continue
            else:
                limpar_a_tela()
                print("A pasta de trabalho e obrigatoria.")
                tentar = input("Deseja tentar novamente? (s/n): ").strip().lower()
                if tentar == 's':
                    continue
                else:
                    print("\nEncerrando o programa... Ate logo!")
                    sys.exit()
        else:
            # Se a pasta já existe, sai do loop e retorna o caminho
            return caminho_completo


# --- TESTADOR DE LINKS ---

def testar_um_link(ticket, link, contexto, cabecalhos, total):
    global contador_processados
    with trava_print:
        contador_processados += 1
        sys.stdout.write(f"\rAnalisando ({contador_processados} / {total})")
        sys.stdout.flush()

    if not link: return None

    if "@" in link and "http" not in link:
        return ("EMAIL", ticket, link, "E-mail Detectado")

    url_final = link if link.startswith(('http://', 'https://')) else 'http://' + link

    try:
        requisicao = urllib.request.Request(url_final, headers=cabecalhos)
        with urllib.request.urlopen(requisicao, timeout=10, context=contexto) as resposta:
            return None
    except urllib.error.HTTPError as erro:
        if erro.code == 403:
            return ("BLOQUEIO", ticket, link, "Bloqueio ou Captcha (403)")
        elif erro.code == 401:
            return ("LOGIN", ticket, link, "Necessita Login (401)")
        elif erro.code == 404:
            return ("QUEBRADO", ticket, link, "Link Quebrado (404)")
        else:
            return ("OUTROS", ticket, link, f"Status HTTP {erro.code}")
    except Exception:
        return ("DOWN", ticket, link, "Site Fora do Ar (Down)")


# --- PROGRAMA PRINCIPAL ---

def programa_principal():
    global contador_processados

    pasta_trabalho = verificar_pasta_trabalho()
    os.chdir(pasta_trabalho)

    contexto_seguro = ssl._create_unverified_context()
    cabecalhos_navegador = {'User-Agent': 'Mozilla/5.0'}

    while True:
        limpar_a_tela()
        contador_processados = 0
        print("=" * 65 + "\n                TESTE DOWN HTTP (TRIAGEM)\n" + "=" * 65)

        while True:
            print("\n(Digite 'sair' para fechar)")
            pergunta_threads = input("Aperte [Enter] para usar 10 threads, ou digite a quantidade (max 50): ").strip()
            verificar_se_quer_sair(pergunta_threads)

            if pergunta_threads == "":
                velocidade = 10
                break
            if pergunta_threads.isdigit():
                velocidade = int(pergunta_threads)
                if 1 <= velocidade <= 50:
                    break
                else:
                    print(f"Erro: Limite excedido! Escolha entre 1 e 50.")
            else:
                print("Erro: Entrada invalida! Digite um numero.")

        while True:
            print("\n(Digite 'sair' para fechar)")
            nome_arq = input("Nome do arquivo CSV: ").strip()
            verificar_se_quer_sair(nome_arq)
            if not nome_arq.lower().endswith('.csv'): nome_arq += ".csv"

            if os.path.exists(nome_arq):
                break
            else:
                print(f"\nErro: Arquivo '{nome_arq}' nao encontrado.")
                print(f"Pasta atual: {os.getcwd()}")
                print("-" * 30)

        try:
            dados_csv = []
            with open(nome_arq, mode='r', encoding='utf-8-sig') as f:
                leitor = csv.DictReader(f)
                for linha in leitor:
                    u = linha.get('URL/IP/Domain', '').strip()
                    if u: dados_csv.append({'ticket': linha.get('KEY', 'N/A'), 'url': u})

            total = len(dados_csv)
            print(f"\nArquivo: {nome_arq}\nIniciando analise...\n")

            todos_erros = []
            with ThreadPoolExecutor(max_workers=velocidade) as executor:
                tarefas = [
                    executor.submit(testar_um_link, d['ticket'], d['url'], contexto_seguro, cabecalhos_navegador, total)
                    for d in dados_csv]
                for t in tarefas:
                    res = t.result()
                    if res: todos_erros.append(res)

            if todos_erros:
                categorias = {"DOWN": [], "EMAIL": [], "QUEBRADO": [], "BLOQUEIO": [], "LOGIN": [], "OUTROS": []}
                for cat, tick, url, mot in todos_erros:
                    categorias[cat].append((tick, url, mot))

                ordem_exibicao = [
                    ("DOWN",
                     "--- [SITES REALMENTE FORA DO AR / DOWN] --- O servidor nao respondeu. O site pode estar fora do ar ou o dominio expirou."),
                    ("EMAIL",
                     "--- [E-MAIL DETECTADO] --- O link encontrado aponta para um endereco de e-mail em vez de um site."),
                    ("QUEBRADO",
                     "--- [LINKS QUEBRADOS (404)] --- O servidor respondeu, mas a pagina especifica nao foi encontrada."),
                    ("BLOQUEIO",
                     "--- [BLOQUEIO OU CAPTCHA (403)] --- O acesso foi negado pelo servidor (protecao contra robos ou regiao)."),
                    ("LOGIN", "--- [NECESSITA LOGIN (401)] --- A pagina exige usuario e senha para ser visualizada."),
                    ("OUTROS", "--- [OUTROS ERROS] --- Erros diversos reportados pelo servidor (Ex: Erro interno 500).")
                ]

                print("\n" + "-" * 65)
                for id_cat, titulo_completo in ordem_exibicao:
                    if categorias[id_cat]:
                        print(f"{titulo_completo}")
                        for tick, url, _ in categorias[id_cat]:
                            print(f"Ticket: {tick} | Link: {url}")
                        print("-" * 30)

                if categorias["DOWN"]:
                    lista_busca = "|".join([u for _, u, _ in categorias["DOWN"]])
                    print("\nLISTA PARA O MULTI FIND (COPIE ABAIXO):")
                    print(lista_busca)

                    if pode_copiar:
                        resp = input("\n[ENTER] para COPIAR ou 'n' para pular: ").strip().lower()
                        verificar_se_quer_sair(resp)
                        if resp != 'n':
                            pyperclip.copy(lista_busca)
                            print("Copiado!")

                print("\nDeseja exportar para CSV?")
                resp_exp = input("[ENTER] para exportar ou 'n' para nao: ").strip().lower()
                verificar_se_quer_sair(resp_exp)

                if resp_exp != 'n':
                    nome_out = f"Analise_{nome_arq}"
                    with open(nome_out, mode='w', encoding='utf-8-sig', newline='') as f_out:
                        escritor = csv.writer(f_out)

                        for id_cat, titulo_completo in ordem_exibicao:
                            if categorias[id_cat]:
                                escritor.writerow([titulo_completo])
                                escritor.writerow(['KEY', 'URL/IP/Domain', 'MOTIVO'])
                                for tick, url, mot in categorias[id_cat]:
                                    escritor.writerow([tick, url, mot])
                                escritor.writerow([])

                    print(f"Arquivo '{nome_out}' exportado com sucesso!")
            else:
                print("\nConcluido! Nenhum erro detectado.")

        except Exception as e:
            print(f"\nErro inesperado: {e}")

        print("\n[ENTER] para nova analise")
        print("(Ou digite 'sair' para fechar)")
        verificar_se_quer_sair(input("Escolha: ").strip())


if __name__ == "__main__":
    programa_principal()