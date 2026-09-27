import sqlite3
import base64
import os
import random
from datetime import datetime, date
import pandas as pd
import streamlit as st
import altair as alt

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="LaBzz - Tycoon Management",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# HELPER & FUNZIONI DATABASE
# ==========================================
DB_NAME = "magazzino.db"

def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prodotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            unita_misura TEXT DEFAULT 'g',
            valore_mercato_unitario REAL DEFAULT 0,
            scorta_minima_g REAL DEFAULT 0
        )""")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prodotto_id INTEGER NOT NULL,
            codice_lotto TEXT NOT NULL,
            quantita_iniziale REAL NOT NULL,
            quantita_attuale REAL NOT NULL,
            costo_acquisto_unitario REAL NOT NULL,
            data_acquisto DATE,
            data_carico DATE NOT NULL,
            data_completamento DATE,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id) ON DELETE CASCADE
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prodotto_id INTEGER NOT NULL,
            lotto_id INTEGER,
            tipo TEXT NOT NULL,
            quantita REAL NOT NULL,
            prezzo_unitario REAL DEFAULT 0,
            ricavo_totale REAL DEFAULT 0,
            costo_totale REAL DEFAULT 0,
            margine REAL DEFAULT 0,
            note TEXT,
            cliente TEXT DEFAULT 'Anonimo',
            pagamento TEXT DEFAULT 'Subito',
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id) ON DELETE CASCADE,
            FOREIGN KEY (lotto_id) REFERENCES lotti (id) ON DELETE SET NULL
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS impostazioni (
            chiave TEXT PRIMARY KEY,
            valore REAL NOT NULL
        )""")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('soglia_esaurimento', 10.0)")

init_db()

def genera_codice_lotto_automatico(data_riferimento=None):
    if data_riferimento is None:
        data_riferimento = date.today()
    
    giorno = data_riferimento.strftime("%d").lstrip("0")
    MESE_INIZIALI = ['g', 'f', 'm', 'a', 'm', 'g', 'l', 'a', 's', 'o', 'n', 'd']
    iniziale_mese = MESE_INIZIALI[data_riferimento.month - 1]
    anno_2_cifre = data_riferimento.strftime("%y")
    
    return f"{giorno}{iniziale_mese}{anno_2_cifre}"

def get_video_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    return None

def get_soglia_esaurimento():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valore FROM impostazioni WHERE chiave = 'soglia_esaurimento'")
        row = cursor.fetchone()
        return float(row[0]) if row else 10.0

def get_prodotti_disponibili_df():
    query = """
        SELECT DISTINCT p.id, p.nome, p.valore_mercato_unitario
        FROM prodotti p
        JOIN lotti l ON p.id = l.prodotto_id
        WHERE l.quantita_attuale > 0
        ORDER BY p.nome ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_prodotti_tutti_df():
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM prodotti ORDER BY nome ASC", conn)

def get_lotti_attivi_df():
    query = """
        SELECT l.id, p.nome AS prodotto, l.codice_lotto, l.quantita_iniziale, l.quantita_attuale, 
               'g' AS unita_misura, l.costo_acquisto_unitario, l.data_acquisto, l.data_carico
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        WHERE l.quantita_attuale > 0
        ORDER BY l.data_carico ASC, l.id ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_report_lotti_integrato_df(soglia_esaurimento_g=10.0):
    query = """
        SELECT 
            l.id AS lotto_id,
            p.nome AS prodotto,
            l.codice_lotto,
            l.quantita_iniziale,
            l.quantita_attuale,
            'g' AS unita_misura,
            l.costo_acquisto_unitario,
            (l.quantita_iniziale * l.costo_acquisto_unitario) AS costo_totale_lotto,
            COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.quantita ELSE 0 END), 0) AS qta_venduta_lotto,
            COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.ricavo_totale ELSE 0 END), 0) AS incasso_totale_lotto,
            COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.margine ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN m.tipo = 'XME' THEN m.costo_totale ELSE 0 END), 0) AS guadagno_netto_lotto,
            l.data_acquisto,
            l.data_carico,
            l.data_completamento
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        LEFT JOIN movimenti m ON l.id = m.lotto_id
        GROUP BY l.id
        ORDER BY l.data_carico DESC, l.id DESC
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)

    if not df.empty:
        def calcola_stato(row):
            qta = float(row['quantita_attuale'])
            if qta == 0:
                dt_comp = row['data_completamento']
                return f"✅ Esaurito ({dt_comp})" if dt_comp else "✅ Esaurito"
            elif qta <= soglia_esaurimento_g:
                return f"⚠️ In Esaurimento ({qta:.1f} g rimasti)"
            else:
                return "🔵 Attivo"

        df['stato_lotto'] = df.apply(calcola_stato, axis=1)

    return df

def get_movimenti_dettagliati_df():
    query = """
        SELECT 
            m.id, 
            m.data, 
            p.nome AS prodotto, 
            COALESCE(l.codice_lotto, 'N/D') AS lotto,
            m.tipo, 
            m.quantita, 
            m.prezzo_unitario AS prezzo_g, 
            m.ricavo_totale AS incasso, 
            m.margine, 
            COALESCE(m.cliente, 'Anonimo') AS cliente,
            COALESCE(m.pagamento, 'Subito') AS stato_pagamento
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        LEFT JOIN lotti l ON m.lotto_id = l.id
        ORDER BY m.data DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def aggiungi_cliente_se_nuovo(nome):
    if nome and nome.strip() != "":
        nome_pulito = nome.strip().capitalize()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO clienti (nome) VALUES (?)", (nome_pulito,))

def calcola_grado_reputazione(rep):
    if rep < 30:
        return "🌱 Principiante di Quartiere"
    elif rep < 60:
        return "🥈 Spacciatore Rispettato"
    elif rep < 85:
        return "🥇 Boss della Zona"
    else:
        return "👑 Re del Quartiere"

def calcola_stato_magazzino(solo_disponibili=False):
    with get_connection() as conn:
        prodotti_df = pd.read_sql_query("SELECT * FROM prodotti", conn)
        lotti_df = pd.read_sql_query("SELECT * FROM lotti WHERE quantita_attuale > 0", conn)
        movimenti_df = pd.read_sql_query("SELECT * FROM movimenti", conn)

    risultati = []
    for _, prod in prodotti_df.iterrows():
        p_id = prod['id']
        lotti_prod = lotti_df[lotti_df['prodotto_id'] == p_id]
        qta_totale = float(lotti_prod['quantita_attuale'].sum())
        
        if solo_disponibili and qta_totale <= 0:
            continue

        valore_costo_totale = float((lotti_prod['quantita_attuale'] * lotti_prod['costo_acquisto_unitario']).sum())
        costo_medio = valore_costo_totale / qta_totale if qta_totale > 0 else 0.0
        valore_mercato_totale = qta_totale * prod['valore_mercato_unitario']
        
        vendite = movimenti_df[(movimenti_df['prodotto_id'] == p_id) & (movimenti_df['tipo'] == 'VENDITA')]
        qta_venduta = float(vendite['quantita'].sum())
        incasso_totale = float(vendite['ricavo_totale'].sum())
        margine_totale = float(vendite['margine'].sum())

        risultati.append({
            'prodotto_id': p_id,
            'prodotto': prod['nome'],
            'unita_misura': 'g',
            'qta_disponibile': qta_totale,
            'scorta_minima_g': float(prod['scorta_minima_g']),
            'costo_medio_ponderato': costo_medio,
            'valore_mercato_unitario': float(prod['valore_mercato_unitario']),
            'valore_totale_costo': valore_costo_totale,
            'valore_totale_mercato': valore_mercato_totale,
            'qta_venduta': qta_venduta,
            'incasso_totale': incasso_totale,
            'margine_totale': margine_totale
        })

    return pd.DataFrame(risultati)

def segna_debito_pagato(nome_cliente):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(ricavo_totale) FROM movimenti WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))
        tot_incassato = cursor.fetchone()[0] or 0.0
        
        cursor.execute("UPDATE movimenti SET pagamento = 'Subito' WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))
        st.session_state.soldi_cassa += tot_incassato

def spara_fuochi_d_artificio():
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <script>
        var count = 200;
        var defaults = { origin: { y: 0.7 } };
        function fire(particleRatio, opts) {
          confetti(Object.assign({}, defaults, opts, {
            particleCount: Math.floor(count * particleRatio)
          }));
        }
        fire(0.25, { spread: 26, startVelocity: 55 });
        fire(0.2, { spread: 60 });
        fire(0.35, { spread: 100, decay: 0.91, scalar: 0.8 });
    </script>
    """
    st.components.v1.html(js_code, height=0)

# ==========================================
# GANGSTER E FORNITORI
# ==========================================
GANGSTER_FORNITORI = [
    {"nome": "Don Cornetto", "frase": "«Un'offerta che non puoi rifiutare... o finisci a fare i cappucci!»"},
    {"nome": "Tony Pesto", "frase": "«O compri questo stock o stasera le cotolette le fai coi denti!»"},
    {"nome": "Al Cacio", "frase": "«Robina fresca fresca di contrabbando, scesa dal camion mezz'ora fa.»"},
    {"nome": "Franky 'Cinque Dita'", "frase": "«Guarda che qualità, sfiorala soltanto e ti senti già ricchissimo!»"},
    {"nome": "Peppe 'u Scannatore", "frase": "«Vedi di fare in fretta prima che arrivi la finanza...»"},
    {"nome": "Luigi 'O Calibro", "frase": "«Prezzo da amico, ma non farmi domande su dove l'ho preso.»"},
    {"nome": "Gaetano 'Er Siringa'", "frase": "«Trattativa pulita, niente sbirri, solo contanti e saluti.»"},
    {"nome": "Mimmo 'Er Cipolla'", "frase": "«Questa ti fa piangere da quanto è buona. Prendi prima che cambi idea!»"}
]

def genera_offerta_fornitore_casuale():
    if st.session_state.fornitori_visti_oggi >= st.session_state.max_fornitori_oggi:
        st.info("Per oggi non ci sono altri contatti disponibili.")
        return

    st.session_state.fornitori_visti_oggi += 1
    gangster = random.choice(GANGSTER_FORNITORI)
    
    categoria_stock = random.choice(["Micro", "Standard", "Volume", "TopQuality"])
    
    if categoria_stock == "Micro":
        p_nome = "Micro Stock (G Inconsueti)"
        qta = float(random.choice([12, 13, 14, 15, 16, 17, 18, 19, 21, 22]))
        costo_u = round(random.uniform(4.50, 5.80), 2)
        tipo_offerta = "⚠️ Pochi grammi al dettaglio"
        valore_mercato_suggerito = float(random.randint(8, 10))

    elif categoria_stock == "Standard":
        p_nome = "Varietà Standard"
        qta = float(random.choice([25, 50, 100]))
        costo_u = round(random.uniform(3.50, 4.50), 2)
        tipo_offerta = "🏷️ Stock Taglio Medio"
        valore_mercato_suggerito = float(random.randint(8, 10))

    elif categoria_stock == "TopQuality":
        p_nome = "Top Quality Special"
        qta = float(random.choice([25, 50, 100]))
        costo_u = round(random.uniform(7.00, 9.50), 2)
        tipo_offerta = "💎 Special Top Quality"
        valore_mercato_suggerito = float(random.randint(12, 15))

    else:
        p_nome = "Stock Volume"
        qta = float(random.choice([150, 200, 250, 300, 500]))
        costo_u = round(random.uniform(2.50, 3.50), 2)
        tipo_offerta = "📦 Stock Volume Gran Taglio"
        valore_mercato_suggerito = float(random.randint(8, 10))

    costo_tot = round(qta * costo_u, 2)

    st.session_state.offerta_fornitore = {
        "fornitore_nome": gangster["nome"],
        "fornitore_frase": gangster["frase"],
        "prodotto_nome": p_nome,
        "quantita": qta,
        "costo_unitario": costo_u,
        "costo_totale": costo_tot,
        "valore_mercato_suggerito": valore_mercato_suggerito,
        "tipo": tipo_offerta,
        "codice_lotto": f"OFF-{random.randint(100,999)}"
    }

def genera_cliente_in_negozio():
    prodotti_tutti = get_prodotti_tutti_df()
    if not prodotti_tutti.empty:
        prod = prodotti_tutti.sample(n=1).iloc[0]
        nomi_clienti = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "ClienteVIP", "Matteo", "Valentina"]
        nome_c = random.choice(nomi_clienti)
        
        qta_req = float(random.choices([1, 2, 5, 10, 15, 20, 30], weights=[25, 30, 25, 12, 4, 3, 1], k=1)[0])
        
        val_ref = float(prod['valore_mercato_unitario'])
        budget_u = val_ref * random.uniform(0.85, 1.35)
        
        st.session_state.cliente_in_negozio = {
            "nome": nome_c,
            "prodotto_id": int(prod['id']),
            "prodotto_nome": prod['nome'],
            "quantita_richiesta": qta_req,
            "budget_max_g": round(budget_u, 2),
            "controfferta_attiva": False
        }
    else:
        st.session_state.cliente_in_negozio = None

def genera_evento_casuale_giorno():
    # 35% di probabilità di un evento casuale (Polizia o VIP) ad inizio giornata
    if random.random() < 0.35:
        evento_tipo = random.choice(["polizia", "vip"])
        if evento_tipo == "polizia":
            st.session_state.evento_attivo = {
                "tipo": "polizia",
                "titolo": "🚨 ALLARTE POSTO DI BLOCCO / CONTROLLI!",
                "testo": "Voci di corridoio dicono che la Finanza sta controllando la zona e fermando i sospetti vicino al locale. C'è tensione alta!"
            }
        else:
            prodotti_disp = get_prodotti_disponibili_df()
            if not prodotti_disp.empty:
                prod_vip = prodotti_disp.sample(n=1).iloc[0]
                qta_vip = float(random.choice([5, 10, 15]))
                prezzo_vip = float(prod_vip['valore_mercato_unitario']) * 1.40
                st.session_state.evento_attivo = {
                    "tipo": "vip",
                    "titolo": "📱 NOTIFICA VIP URGENTE",
                    "testo": f"Un cliente VIP misterioso ti ha scritto sul telefono: «Mi servono urgentemente **{qta_vip}g di {prod_vip['nome']}**. Ti pago a peso d'oro (**€{prezzo_vip:.2f}/g**) se me li procuri oggi stesso!»",
                    "prodotto_id": int(prod_vip['id']),
                    "prodotto_nome": prod_vip['nome'],
                    "quantita": qta_vip,
                    "prezzo_offerto": prezzo_vip
                }
    else:
        st.session_state.evento_attivo = None

def esegui_transazione_vendita(cli_att, prezzo_per_g, tipo_pagamento):
    aggiungi_cliente_se_nuovo(cli_att['nome'])
    with get_connection() as conn:
        cursor = conn.cursor()
        lotti_df = pd.read_sql_query("SELECT id, quantita_attuale, costo_acquisto_unitario, codice_lotto FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", conn, params=(cli_att['prodotto_id'],))
        
        qta_da_scaricare = cli_att['quantita_richiesta']
        totale_incasso = 0.0
        
        for _, lotto in lotti_df.iterrows():
            if qta_da_scaricare <= 0: break
            l_id = int(lotto['id'])
            qta_lotto_disp = float(lotto['quantita_attuale'])
            prelievo = min(qta_lotto_disp, qta_da_scaricare)
            nuova_qta = qta_lotto_disp - prelievo
            qta_da_scaricare -= prelievo
            
            ricavo_q = prelievo * prezzo_per_g
            costo_q = prelievo * float(lotto['costo_acquisto_unitario'])
            margine_q = ricavo_q - costo_q
            totale_incasso += ricavo_q
            
            if nuova_qta == 0:
                cursor.execute("UPDATE lotti SET quantita_attuale = 0, data_completamento = ? WHERE id = ?", (date.today(), l_id))
            else:
                cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, l_id))
            
            cursor.execute("""
                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note)
                VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cli_att['prodotto_id'], l_id, prelievo, prezzo_per_g, ricavo_q, costo_q, margine_q, cli_att['nome'], tipo_pagamento, f"Lotto {lotto['codice_lotto']}"))

    if tipo_pagamento == "Subito":
        st.session_state.soldi_cassa += totale_incasso

    st.session_state.energia = max(0, st.session_state.energia - 10)
    st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 3)
    st.session_state.reputazione = min(100, st.session_state.reputazione + 1)
    aggiungi_log(f"✅ VENDITA: {cli_att['nome']} ha comprato {cli_att['quantita_richiesta']}g di '{cli_att['prodotto_nome']}' a €{prezzo_per_g:.2f}/g (+€{totale_incasso:.2f})")
    spara_fuochi_d_artificio()

# INITIAL STATE
if 'soldi_cassa' not in st.session_state:
    st.session_state.soldi_cassa = 200.0
if 'energia' not in st.session_state:
    st.session_state.energia = 100
if 'giorno' not in st.session_state:
    st.session_state.giorno = 1
if 'reputazione' not in st.session_state:
    st.session_state.reputazione = 15
if 'fedelta_clienti' not in st.session_state:
    st.session_state.fedelta_clienti = 10
if 'log_gioco' not in st.session_state:
    st.session_state.log_gioco = ["🎮 Benvenuto nel mondo Tycoon! Capitale iniziale: €200."]
if 'offerta_fornitore' not in st.session_state:
    st.session_state.offerta_fornitore = None
if 'cliente_in_negozio' not in st.session_state:
    st.session_state.cliente_in_negozio = None
if 'fornitori_visti_oggi' not in st.session_state:
    st.session_state.fornitori_visti_oggi = 0
if 'max_fornitori_oggi' not in st.session_state:
    st.session_state.max_fornitori_oggi = random.choice([0, 1, 1, 2])
if 'evento_attivo' not in st.session_state:
    st.session_state.evento_attivo = None
if 'minigioco_trattativa' not in st.session_state:
    st.session_state.minigioco_trattativa = False

if st.session_state.cliente_in_negozio is None:
    genera_cliente_in_negozio()

if st.session_state.giorno == 1 and st.session_state.offerta_fornitore is None and st.session_state.max_fornitori_oggi > 0:
    genera_offerta_fornitore_casuale()
    genera_evento_casuale_giorno()

def aggiungi_log(testo):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.log_gioco.insert(0, f"[{timestamp}] {testo}")

def reset_completo_nuova_partita():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimenti;")
        cursor.execute("DELETE FROM lotti;")
        cursor.execute("DELETE FROM prodotti;")
        cursor.execute("DELETE FROM clienti;")
        
        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario, scorta_minima_g) VALUES ('Varietà Iniziale', 9.0, 20.0);")
        p_id = cursor.lastrowid
        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, 'START-01', 50.0, 50.0, 3.50, ?, ?);", (p_id, date.today(), date.today()))
        l_id = cursor.lastrowid
        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', 50.0, 175.0, 'Fornitore Iniziale', 'Stock Start')", (p_id, l_id))
    
    st.session_state.soldi_cassa = 200.0
    st.session_state.giorno = 1
    st.session_state.energia = 100
    st.session_state.reputazione = 15
    st.session_state.fedelta_clienti = 10
    st.session_state.log_gioco = ["✨ Nuova Partita Iniziata! Reset completo eseguito. Budget: €200."]
    st.session_state.offerta_fornitore = None
    st.session_state.cliente_in_negozio = None
    st.session_state.fornitori_visti_oggi = 0
    st.session_state.max_fornitori_oggi = random.choice([0, 1, 2])
    st.session_state.evento_attivo = None
    st.session_state.minigioco_trattativa = False
    if st.session_state.max_fornitori_oggi > 0:
        genera_offerta_fornitore_casuale()
    genera_cliente_in_negozio()
    genera_evento_casuale_giorno()

# ==========================================
# INIEZIONE CSS CUSTOM ORIGINALE
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Titan+One&display=swap');

    .stApp {
        background-color: #090c17 !important;
        background: linear-gradient(180deg, #070a14 0%, #090c17 50%, #0d1222 100%) !important;
        color: #f8fafc !important;
        font-family: 'Fredoka', sans-serif !important;
        font-weight: 500;
    }

    header[data-testid="stHeader"] {
        display: none !important;
    }

    .block-container {
        padding-top: 2.8rem !important;
        padding-bottom: 6rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    .logo-container {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0 auto 1.5rem auto !important;
        padding: 0 !important;
    }

    .logo-container video {
        display: block !important;
        margin: 0 auto !important;
        max-width: 420px !important;
        width: 100% !important;
        height: auto !important;
        border-radius: 12px !important;
        object-fit: contain !important;
        background-color: transparent !important;
    }

    div[data-testid="stTabs"] {
        margin-top: 0rem !important;
        padding-top: 0rem !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 10px !important;
        background-color: transparent !important;
        border-bottom: none !important;
        padding: 0px 0 12px 0 !important;
        justify-content: center !important;
        flex-wrap: wrap !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Titan One', cursive, sans-serif !important;
        color: #ffffff !important;
        text-align: center !important;
        line-height: 1.4 !important;
        margin-top: 15px !important;
        margin-bottom: 15px !important;
    }

    .top-metrics-grid {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 10px !important;
        width: 100% !important;
        margin-bottom: 20px !important;
    }

    .dashboard-grid {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 12px !important;
        width: 100% !important;
        margin-bottom: 25px !important;
    }

    .custom-card {
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 10px 8px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
    }

    .card-label {
        color: #94a3b8 !important;
        font-size: 0.70rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        margin-bottom: 4px !important;
    }

    .card-value {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: #38bdf8 !important;
    }

    .card-subtext {
        font-size: 0.70rem !important;
        color: #38bdf8 !important;
        font-weight: 600 !important;
        margin-top: 2px !important;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'Fredoka', sans-serif !important;
        background: rgba(15, 23, 42, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 14px !important;
        color: #94a3b8 !important;
        font-weight: 700 !important;
        padding: 10px 16px !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%) !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# RENDER LOGO IN CIMA
# ==========================================
video_b64 = get_video_base64("logo.gif.mp4")

if video_b64:
    st.markdown(f"""
        <div class="logo-container">
            <video autoplay loop muted playsinline>
                <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
            </video>
        </div>
    """, unsafe_allow_html=True)
else:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.title("LaBzz Tycoon")

# ==========================================
# HEADER METRICHE TYCOON GRIGLIA COMPATTA
# ==========================================
with get_connection() as conn:
    df_lotti_scorte = pd.read_sql_query("""
        SELECT p.nome, SUM(l.quantita_attuale) as qta 
        FROM lotti l 
        JOIN prodotti p ON l.prodotto_id = p.id 
        WHERE l.quantita_attuale > 0 
        GROUP BY p.nome
    """, conn)

qta_totale_magazzino = df_lotti_scorte['qta'].sum() if not df_lotti_scorte.empty else 0.0
qta_top_quality = df_lotti_scorte[df_lotti_scorte['nome'].str.contains("Top Quality", case=False, na=False)]['qta'].sum() if not df_lotti_scorte.empty else 0.0
grado_rep_testo = calcola_grado_reputazione(st.session_state.reputazione)

st.markdown(f"""
<div class="top-metrics-grid">
    <div class="custom-card">
        <div class="card-label">💵 Cassa Liquida</div>
        <div class="card-value">€ {st.session_state.soldi_cassa:,.2f}</div>
    </div>
    <div class="custom-card">
        <div class="card-label">📦 Scorte Magazzino</div>
        <div class="card-value">{qta_totale_magazzino:.1f} g</div>
        <div class="card-subtext">⭐ {qta_top_quality:.1f} g Top Quality</div>
    </div>
    <div class="custom-card">
        <div class="card-label">📅 Turno / Giorno</div>
        <div class="card-value">Giorno {st.session_state.giorno}</div>
    </div>
    <div class="custom-card">
        <div class="card-label">⚡ Energia</div>
        <div class="card-value">{st.session_state.energia}%</div>
    </div>
    <div class="custom-card" style="grid-column: span 2;">
        <div class="card-label">⭐ Reputazione e Rango</div>
        <div class="card-value">{st.session_state.reputazione} / 100 ({grado_rep_testo})</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# GESTIONE EVENTI SPECIALI (POLIZIA / VIP) IN EVIDENZA
# ==========================================
if st.session_state.evento_attivo:
    ev = st.session_state.evento_attivo
    with st.container(border=True):
        st.markdown(f"### {ev['titolo']}")
        st.write(ev['testo'])
        
        if ev['tipo'] == 'polizia':
            col_ev1, col_ev2, col_ev3 = st.columns(3)
            with col_ev1:
                if st.button("💰 Paga Tangente (€45)", use_container_width=True):
                    if st.session_state.soldi_cassa >= 45.0:
                        st.session_state.soldi_cassa -= 45.0
                        st.success("Hai corrotto la pattuglia! Sgomberati i controlli.")
                        aggiungi_log("🚨 POLIZIA: Pagata tangente di €45 per evitare guai.")
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error("Non hai abbastanza contanti per la tangente!")
            with col_ev2:
                if st.button("🏃 Rischia e Nascondi Merce", use_container_width=True):
                    if random.random() < 0.55:
                        st.success("Sei riuscito a nascondere tutto in tempo! Sgommati senza danni.")
                        aggiungi_log("🚨 POLIZIA: Controlli superati nascondendo la merce.")
                    else:
                        st.warning("Ti hanno perquisito il magazzino e sequestrato un po' di scorte!")
                        aggiungi_log("🚨 POLIZIA: Perquisizione subita! Perdita parziale di scorte.")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE lotti SET quantita_attuale = MAX(0.0, quantita_attuale - 5.0) WHERE quantita_attuale > 0 LIMIT 2")
                    st.session_state.evento_attivo = None
                    st.rerun()
            with col_ev3:
                if st.button("🚪 Chiudi Locale per Oggi", use_container_width=True):
                    st.info("Hai tenuto chiuso per evitare rogne. Giornata persa.")
                    aggiungi_log("🚨 POLIZIA: Locale chiuso per l'intera giornata.")
                    st.session_state.evento_attivo = None
                    st.rerun()

        elif ev['tipo'] == 'vip':
            col_vip1, col_vip2 = st.columns(2)
            with col_vip1:
                if st.button("✅ ACCETTA ORDINE VIP", use_container_width=True):
                    # Verifica se ha abbastanza scorte
                    with get_connection() as conn:
                        qta_disp_vip = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(ev['prodotto_id'],)).iloc[0, 0]
                    qta_disp_vip = float(qta_disp_vip) if qta_disp_vip else 0.0
                    
                    if qta_disp_vip >= ev['quantita']:
                        # Esegui vendita VIP istantanea
                        cli_vip_obj = {"nome": "Cliente VIP", "prodotto_id": ev['prodotto_id'], "prodotto_nome": ev['prodotto_nome'], "quantita_richiesta": ev['quantita']}
                        esegui_transazione_vendita(cli_vip_obj, ev['prezzo_offerto'], "Subito")
                        st.success(f"🎉 Ordine VIP completato con successo! Incasso super: €{ev['quantita'] * ev['prezzo_offerto']:.2f}")
                        st.session_state.reputazione = min(100, st.session_state.reputazione + 4)
                        aggiungi_log(f"📱 VIP: Completato ordine speciale di {ev['quantita']}g di {ev['prodotto_nome']}.")
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error(f"Non hai abbastanza scorte di {ev['prodotto_nome']} (Disponibili: {qta_disp_vip:.1f}g)!")
            with col_vip2:
                if st.button("❌ RIFIUTA ORDINE", use_container_width=True):
                    st.info("Hai declinato l'offerta VIP.")
                    st.session_state.evento_attivo = None
                    st.rerun()

# ==========================================
# SCHEDE / TAB DELL'APPLICAZIONE
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💸 Cassa", 
    "📊 Dashboard", 
    "🚚 Rifornimenti & Fornitori",
    "📈 Statistiche",
    "📜 Report & Storico"
])

# ------------------------------------------
# TAB 1: CASSA OPERATIVA
# ------------------------------------------
with tab1:
    col_cassa, col_ledger = st.columns([1.2, 1])
    
    with col_cassa:
        st.subheader("💸 Cassa Operativa")
        
        tipo_operazione = st.radio("Seleziona Modalità", ["Incontra Cliente (Manuale)", "Automazione Turno AI", "XME (Perk)"], horizontal=True)
        
        if tipo_operazione == "Incontra Cliente (Manuale)":
            st.markdown("##### 👤 Cliente Attualmente alla Cassa")
            
            cli_att = st.session_state.cliente_in_negozio
            if cli_att:
                with st.container(border=True):
                    st.markdown(f"### **{cli_att['nome']}** è qui per comprare!")
                    st.write(f"• **Varietà Richiesta:** ⭐ **{cli_att['prodotto_nome']}**")
                    st.write(f"• **Quantità Richiesta:** {cli_att['quantita_richiesta']} g")
                    
                    with get_connection() as conn:
                        qta_disp_query = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(cli_att['prodotto_id'],)).iloc[0, 0]
                        costo_lotto_ref = pd.read_sql_query("SELECT costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC LIMIT 1", conn, params=(cli_att['prodotto_id'],))
                        
                    qta_disp_tot = float(qta_disp_query) if (qta_disp_query is not None and not pd.isna(qta_disp_query)) else 0.0
                    costo_base_u = float(costo_lotto_ref.iloc[0,0]) if not costo_lotto_ref.empty else 0.0

                    if qta_disp_tot < cli_att['quantita_richiesta']:
                        st.error(f"❌ NON HAI QUESTO PRODOTTO IN MAGAZZINO! (Disponibili: {qta_disp_tot:.1f}g di {cli_att['prodotto_nome']})")
                        st.write(f"«Pessimo servizio! Volevo proprio della **{cli_att['prodotto_nome']}**. Tornerò quando ti sarai rifornito!»")
                        
                        if st.button("👋 Congeda Cliente Deluso", use_container_width=True):
                            st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 1)
                            aggiungi_log(f"⚠️ VENDITA FALLITA: {cli_att['nome']} voleva {cli_att['prodotto_nome']} ma non ne avevi abbastanza.")
                            genera_cliente_in_negozio()
                            st.rerun()

                    else:
                        st.info(f"Disponibilità in magazzino: {qta_disp_tot:.1f} g di {cli_att['prodotto_nome']}")
                        
                        if cli_att.get("controfferta_attiva", False):
                            st.warning(f"🗣️ **CONTROFFERTA DI {cli_att['nome'].upper()}:**")
                            st.write(f"«Troppo caro! Io ti offro **€ {cli_att['budget_max_g']:.2f} / g** per {cli_att['quantita_richiesta']}g di **{cli_att['prodotto_nome']}**.»")
                            
                            incasso_contro = cli_att['budget_max_g'] * cli_att['quantita_richiesta']
                            costo_tot_contro = costo_base_u * cli_att['quantita_richiesta']
                            margine_contro = incasso_contro - costo_tot_contro
                            
                            st.markdown("##### 🧮 I tuoi conti sulla controfferta:")
                            col_c1, col_c2, col_c3 = st.columns(3)
                            col_c1.metric("Incasso Totale", f"€ {incasso_contro:.2f}")
                            col_c2.metric("Costo Stock", f"€ {costo_tot_contro:.2f}")
                            col_c3.metric("Guadagno Netto", f"€ {margine_contro:.2f}")

                            tipo_pagamento = st.radio("Modalità Pagamento", ["Subito", "Dopo (Credito)"], horizontal=True, key="pag_contro")

                            col_co1, col_co2 = st.columns(2)
                            with col_co1:
                                if st.button("✅ ACCETTA CONTROFFERTA", use_container_width=True):
                                    esegui_transazione_vendita(cli_att, cli_att['budget_max_g'], tipo_pagamento)
                                    st.success("Accettata la controfferta del cliente!")
                                    genera_cliente_in_negozio()
                                    st.rerun()
                            with col_co2:
                                if st.button("❌ RIFIUTA E MANDA VIA", use_container_width=True):
                                    st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 2)
                                    aggiungi_log(f"❌ RIFIUTATO: Rifiutata controfferta di {cli_att['nome']}")
                                    st.info("Hai rifiutato la controfferta. Il cliente è andato via.")
                                    genera_cliente_in_negozio()
                                    st.rerun()

                        else:
                            prezzo_proposto = st.number_input("Imposta il Tuo Prezzo al Grammo (€/g)", min_value=0.5, value=float(cli_att['budget_max_g']), step=0.5, format="%.2f")
                            totale_proposto = prezzo_proposto * cli_att['quantita_richiesta']
                            st.write(f"**Totale Incasso Proposto:** € {totale_proposto:.2f}")

                            tipo_pagamento = st.radio("Modalità Pagamento", ["Subito", "Dopo (Credito)"], horizontal=True, key="pag_init")

                            col_act1, col_act2 = st.columns(2)
                            with col_act1:
                                if st.button("🤝 Proponi Offerta e Vendi", use_container_width=True):
                                    if prezzo_proposto <= cli_att['budget_max_g']:
                                        esegui_transazione_vendita(cli_att, prezzo_proposto, tipo_pagamento)
                                        st.success(f"🎉 {cli_att['nome']} ha ACCETTATO!")
                                        genera_cliente_in_negozio()
                                        st.rerun()
                                    else:
                                        st.session_state.cliente_in_negozio['controfferta_attiva'] = True
                                        st.warning(f"⚠️ {cli_att['nome']} ritiene la cifra alta e ti sta facendo una controfferta!")
                                        st.rerun()

                            with col_act2:
                                if st.button("🚪 Rifiuta / Prossimo", use_container_width=True):
                                    st.info("Cliente congedato.")
                                    genera_cliente_in_negozio()
                                    st.rerun()

        elif tipo_operazione == "Automazione Turno AI":
            st.markdown("##### 🏪 Automazione Sales Engine")
            strategia_bot = st.selectbox("Strategia Bot", ["Onesta / Valore di Mercato", "Aggressiva (+20%)", "Generosa (-15%)"])

            if st.button("🚀 Avvia Automazione Turno (-20% Energia)", use_container_width=True):
                if st.session_state.energia < 20:
                    st.error("Sei troppo stanco! Riposa.")
                else:
                    st.session_state.energia -= 20
                    prodotti_tutti = get_prodotti_tutti_df()
                    
                    if not prodotti_tutti.empty:
                        num_clienti_tot = random.randint(3, 7) + int(st.session_state.fedelta_clienti / 15)
                        clienti_nomi = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "ClienteVIP", "Matteo"]
                        vendite_ok = 0
                        
                        for _ in range(num_clienti_tot):
                            prod_req = prodotti_tutti.sample(n=1).iloc[0]
                            p_id = int(prod_req['id'])
                            p_nome = prod_req['nome']
                            val_m = float(prod_req['valore_mercato_unitario'])
                            cli_nome = random.choice(clienti_nomi)
                            
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", (p_id,))
                                lotti = cursor.fetchall()
                                
                                if not lotti: continue
                                
                                prezzo_bot = val_m * 1.25 if "Aggressiva" in strategia_bot else (val_m * 0.85 if "Generosa" in strategia_bot else val_m)
                                budget_cli = val_m * random.uniform(0.85, 1.35) * (1 + (st.session_state.fedelta_clienti / 200))
                                
                                if prezzo_bot <= budget_cli:
                                    qta_req = float(random.choices([1, 2, 5, 10, 15, 20], weights=[30, 30, 25, 10, 3, 2], k=1)[0])
                                    qta_req = min(lotti[0][1], qta_req)
                                    if qta_req <= 0: continue
                                    
                                    l_id, l_qta, l_costo = lotti[0]
                                    cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale - ? WHERE id = ?", (qta_req, l_id))
                                    ricavo = qta_req * prezzo_bot
                                    margine = ricavo - (qta_req * l_costo)
                                    
                                    cursor.execute("""
                                        INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento)
                                        VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, 'Subito')
                                    """, (p_id, l_id, qta_req, prezzo_bot, ricavo, qta_req * l_costo, margine, cli_nome))
                                    
                                    st.session_state.soldi_cassa += ricavo
                                    vendite_ok += 1
                                    aggiungi_log(f"✅ BOT: {cli_nome} ha comprato {qta_req}g di '{p_nome}' (+€{ricavo:.2f})")

                        if vendite_ok > 0:
                            st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 4)
                            st.session_state.reputazione = min(100, st.session_state.reputazione + 2)
                            st.success(f"Turno IA Completato! Serviti {vendite_ok} clienti.")

                    st.rerun()

        elif tipo_operazione == "XME":
            st.markdown("##### 🧪 Registra Uso Personale XME (+30% Energia)")
            lotti_df = get_lotti_attivi_df()
            if not lotti_df.empty:
                with st.form("form_xme"):
                    opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                    lotto_sel = st.selectbox("Seleziona Lotto", list(opzioni_lotto.keys()))
                    lotto_id = opzioni_lotto[lotto_sel]
                    qta_xme = st.number_input("Quantità (g)", min_value=0.5, value=5.0, step=0.5)

                    if st.form_submit_button("Conferma Uscita XME"):
                        lotto_row = lotti_df[lotti_df['id'] == lotto_id].iloc[0]
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            nuova_q = float(lotto_row['quantita_attuale']) - qta_xme
                            p_id = int(get_prodotti_tutti_df()[get_prodotti_tutti_df()['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                            cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_q, lotto_id))
                            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, margine, cliente, note) VALUES (?, ?, 'XME', ?, ?, ?, 'XME', 'Consumo Perk')", (p_id, lotto_id, qta_xme, qta_xme * float(lotto_row['costo_acquisto_unitario']), -qta_xme * float(lotto_row['costo_acquisto_unitario'])))
                        
                        st.session_state.energia = min(100, st.session_state.energia + 30)
                        aggiungi_log(f"🧪 XME: Consumati {qta_xme}g dal lotto.")
                        st.rerun()

        st.markdown("---")
        st.markdown("### 💤 Turno Notturno")
        if st.button("🌙 Riposa e Passa al Giorno Successivo", use_container_width=True):
            st.session_state.giorno += 1
            st.session_state.energia = 100
            
            st.session_state.offerta_fornitore = None
            st.session_state.fornitori_visti_oggi = 0
            st.session_state.max_fornitori_oggi = random.choice([0, 1, 1, 2])
            st.session_state.minigioco_trattativa = False
            
            if st.session_state.max_fornitori_oggi > 0 and random.random() < 0.60:
                genera_offerta_fornitore_casuale()
                
            genera_cliente_in_negozio()
            genera_evento_casuale_giorno()
            aggiungi_log(f"🌙 Giorno {st.session_state.giorno} iniziato. Energia 100%. Fornitori disponibili oggi: {st.session_state.max_fornitori_oggi}")
            st.rerun()

    # --------------------------------------
    # COLONNA 2: LEDGER LIVE & EVENT LOG
    # --------------------------------------
    with col_ledger:
        st.subheader("📖 Ledger & Movimenti Live")
        
        movimenti_df = get_movimenti_dettagliati_df()
        if not movimenti_df.empty:
            st.dataframe(
                movimenti_df[['data', 'cliente', 'tipo', 'prodotto', 'quantita', 'incasso', 'margine']],
                use_container_width=True,
                hide_index=True,
                height=300
            )
        else:
            st.info("Nessun movimento registrato nel ledger.")

        st.markdown("##### 📜 Registro Eventi Turno")
        with st.container(border=True):
            for log in st.session_state.log_gioco[:10]:
                st.caption(log)

# ------------------------------------------
# TAB 2: DASHBOARD & ANALYTICS
# ------------------------------------------
with tab2:
    st.subheader("📊 Dashboard & Analytics")
    df_stato_disp = calcola_stato_magazzino(solo_disponibili=True)
    movimenti_df = get_movimenti_dettagliati_df()

    if not df_stato_disp.empty or not movimenti_df.empty:
        val_costo = df_stato_disp['valore_totale_costo'].sum() if not df_stato_disp.empty else 0
        val_mercato = df_stato_disp['valore_totale_mercato'].sum() if not df_stato_disp.empty else 0
        incasso_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['incasso'].sum() if not movimenti_df.empty else 0
        margine_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['margine'].sum() if not movimenti_df.empty else 0

        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="custom-card"><div class="card-label">Valore (Costo)</div><div class="card-value">€ {val_costo:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Valore (Vendita)</div><div class="card-value">€ {val_mercato:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Incasso Totale</div><div class="card-value">€ {incasso_tot:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Margine Netto</div><div class="card-value">€ {margine_tot:,.2f}</div></div>
        </div>
        """, unsafe_allow_html=True)

        if not movimenti_df.empty:
            mov_df = movimenti_df.copy()
            mov_df['Data_Ora'] = pd.to_datetime(mov_df['data'])
            mov_df = mov_df.sort_values('Data_Ora')
            mov_df['Incasso Totale'] = mov_df['incasso'].cumsum()
            mov_df['Margine Netto'] = mov_df['margine'].cumsum()
            
            chart_df = mov_df.melt(id_vars=['Data_Ora', 'prodotto', 'tipo'], value_vars=['Incasso Totale', 'Margine Netto'], var_name='Metrica', value_name='Valore (€)')
            chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Data_Ora:T', title='Data e Ora'), y=alt.Y('Valore (€):Q', title='Importo (€)'),
                color=alt.Color('Metrica:N', scale=alt.Scale(domain=['Incasso Totale', 'Margine Netto'], range=['#2ed573', '#38bdf8']))
            ).properties(height=350).interactive()
            st.altair_chart(chart, use_container_width=True)

# ------------------------------------------
# TAB 3: RIFORNIMENTI & FORNITORI GANGSTER
# ------------------------------------------
with tab3:
    st.subheader("🚚 Rifornimenti & Mercato Nero Fornitori")
    
    if st.session_state.offerta_fornitore:
        off = st.session_state.offerta_fornitore
        costo_tot = off['costo_totale']
        ha_abbastanza_soldi = st.session_state.soldi_cassa >= costo_tot

        with st.container(border=True):
            st.markdown(f"### 🕶️ **{off['fornitore_nome']}** è qui per affari!")
            st.caption(f"_{off['fornitore_frase']}_")
            
            col_off1, col_off2, col_off3 = st.columns(3)
            col_off1.metric("Varietà Proposta", off['prodotto_nome'], off['tipo'])
            col_off2.metric("Quantità Lotto", f"{off['quantita']:,.1f} g")
            col_off3.metric("Prezzo al Grammo", f"€ {off['costo_unitario']:.2f} / g")

            st.markdown(f"#### **Costo Totale Intero Lotto:** € {costo_tot:,.2f}")
            
            if not ha_abbastanza_soldi:
                st.warning(f"⚠️ Non hai abbastanza contanti (€{st.session_state.soldi_cassa:.2f}) per l'intero lotto da €{costo_tot:.2f}. Puoi chiedere un taglio minore!")

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("✅ COMPRA L'INTERO LOTTO", use_container_width=True, disabled=not ha_abbastanza_soldi):
                    st.session_state.soldi_cassa -= costo_tot
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR IGNORE INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (off['prodotto_nome'], off['valore_mercato_suggerito']))
                        cursor.execute("SELECT id FROM prodotti WHERE nome = ?", (off['prodotto_nome'],))
                        p_id = cursor.fetchone()[0]

                        cursor.execute("""
                            INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (p_id, off['codice_lotto'], off['quantita'], off['quantita'], off['costo_unitario'], date.today(), date.today()))
                        l_id = cursor.lastrowid
                        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', ?, ?, ?, 'Acquisto Intero Lotto')", (p_id, l_id, off['quantita'], costo_tot, off['fornitore_nome']))

                    aggiungi_log(f"🚚 ACQUISTO: Comprati {off['quantita']}g di {off['prodotto_nome']} da {off['fornitore_nome']} per €{costo_tot:.2f}")
                    st.success(f"✅ Offerta accettata da {off['fornitore_nome']}!")
                    st.session_state.offerta_fornitore = None
                    st.session_state.minigioco_trattativa = False
                    st.rerun()

            with col_b2:
                if st.button("❌ RIFIUTA E MANDALO VIA", use_container_width=True):
                    aggiungi_log(f"❌ Rifiutata offerta di {off['fornitore_nome']} (l'offerta è scaduta).")
                    st.info(f"Hai mandato via {off['fornitore_nome']}. Se n'è andato.")
                    st.session_state.offerta_fornitore = None
                    st.session_state.minigioco_trattativa = False
                    st.rerun()

            # --- MINIGIOCO DI TRATTATIVA CON IL FORNITORE ---
            st.markdown("---")
            with st.expander("🎲 Avvia Trattativa / Taglio Minore (Minigioco)"):
                st.write("«Vuoi trattare sul prezzo o chiedere una quantità ridotta? Scegli la tua mossa di negoziazione!»")
                
                qta_ridotta = st.number_input("Quanti grammi vuoi chiedere?", min_value=1.0, max_value=float(off['quantita'] - 1.0), value=min(10.0, float(off['quantita'] - 1.0)), step=1.0)
                
                # Selezione approccio di negoziazione
                approccio = st.radio("Stile di Negoziazione", [
                    "🤝 Diplomazia (Prezzo onesto, basso rischio)", 
                    "😎 Sicurezza (+ Sconto fortuna se azzecchi il bluff)", 
                    "🔥 Sfacciato (Rischio alto di farti mandare via)"
                ])
                
                if st.button("🎲 Tira per Negoziare con il Fornitore", use_container_width=True):
                    # Calcolo bonus basato su reputazione e stile
                    tiro = random.randint(1, 100) + int(st.session_state.reputazione / 3)
                    
                    if "Diplomazia" in approccio:
                        sconto = 0.95 if tiro > 40 else 1.10
                        esito_txt = "Il fornitore apprezza i modi civili."
                    elif "Sicurezza" in approccio:
                        sconto = 0.85 if tiro > 65 else 1.20
                        esito_txt = "Hai giocato d'azzardo sulla simpatia."
                    else:
                        sconto = 0.75 if tiro > 85 else 1.35
                        esito_txt = "Sei stato molto sfacciato con il gangster!"
                        
                    nuovo_costo_u = round(off['costo_unitario'] * sconto, 2)
                    nuovo_costo_tot = round(qta_ridotta * nuovo_costo_u, 2)
                    
                    st.session_state.minigioco_risultato = {
                        "qta": qta_ridotta,
                        "costo_u": nuovo_costo_u,
                        "costo_tot": nuovo_costo_tot,
                        "testo_esito": esito_txt,
                        "successo_trattativa": sconto <= 1.15
                    }
                    st.rerun()

                if 'minigioco_risultato' in st.session_state and st.session_state.minigioco_risultato:
                    res = st.session_state.minigioco_risultato
                    st.info(f"🗣️ **Risultato:** {res['testo_esito']} -> **€{res['costo_u']:.2f}/g** (Totale: **€{res['costo_tot']:.2f}**)")
                    
                    ha_soldi_trattativa = st.session_state.soldi_cassa >= res['costo_tot']
                    if st.button("✅ CONFERMA ACQUISTO TRATTATO", use_container_width=True, disabled=not ha_soldi_trattativa):
                        st.session_state.soldi_cassa -= res['costo_tot']
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR IGNORE INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (off['prodotto_nome'], off['valore_mercato_suggerito']))
                            cursor.execute("SELECT id FROM prodotti WHERE nome = ?", (off['prodotto_nome'],))
                            p_id = cursor.fetchone()[0]

                            cursor.execute("""
                                INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (p_id, f"{off['codice_lotto']}-TRATT", res['qta'], res['qta'], res['costo_u'], date.today(), date.today()))
                            l_id = cursor.lastrowid
                            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', ?, ?, ?, 'Acquisto Trattato')", (p_id, l_id, res['qta'], res['costo_tot'], off['fornitore_nome']))

                        aggiungi_log(f"🚚 ACQUISTO TRATTATO: {res['qta']}g di {off['prodotto_nome']} da {off['fornitore_nome']} per €{res['costo_tot']:.2f}")
                        st.success("✅ Trattativa conclusa con successo!")
                        st.session_state.offerta_fornitore = None
                        st.session_state.minigioco_risultato = None
                        st.rerun()

    else:
        fornitori_rimasti = st.session_state.max_fornitori_oggi - st.session_state.fornitori_visti_oggi
        if fornitori_rimasti > 0:
            st.info(f"Oggi puoi ancora ricevere fino a {fornitori_rimasti} contatto/i di fornitori.")
            if st.button("📞 Cerca Contatto Fornitore", use_container_width=True):
                genera_offerta_fornitore_casuale()
                st.rerun()
        else:
            st.warning("⚠️ Per oggi nessun fornitore è disponibile o disposto ad incontrarti. Riposa per passare al giorno successivo.")

    st.markdown("---")
    st.markdown("### 📋 Stato Lotti e Scorte Attuali")
    soglia_attuale = get_soglia_esaurimento()
    report_lotti_df = get_report_lotti_integrato_df(soglia_esaurimento_g=soglia_attuale)
    
    if not report_lotti_df.empty:
        st.dataframe(report_lotti_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    with st.expander("➕ Inserimento Manuale Lotto (Emergenza)"):
        with st.form("form_nuovo_prodotto_lotto"):
            nome_nuovo = st.text_input("Nome Prodotto")
            data_acq_m = st.date_input("Data Acquisto", value=date.today())
            cod_lotto_m = st.text_input("Codice Lotto", value=genera_codice_lotto_automatico(data_acq_m))
            qta_lotto_m = st.number_input("Quantità (g)", value=25.0)
            costo_u_lotto_m = st.number_input("Costo d'Acquisto (€/g)", value=4.0)
            prezzo_v_init = st.number_input("Prezzo Vendita (€/g)", value=9.0)

            if st.form_submit_button("Crea Prodotto e Registra Lotto"):
                costo_t_m = qta_lotto_m * costo_u_lotto_m
                if st.session_state.soldi_cassa < costo_t_m:
                    st.error("Fondi insufficienti in cassa!")
                else:
                    st.session_state.soldi_cassa -= costo_t_m
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (nome_nuovo.strip(), prezzo_v_init))
                        p_id = cursor.lastrowid
                        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, ?, ?, ?, ?, ?, ?)", (p_id, cod_lotto_m.strip(), qta_lotto_m, qta_lotto_m, costo_u_lotto_m, data_acq_m, date.today()))
                        lotto_id = cursor.lastrowid
                        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente) VALUES (?, ?, 'CARICO', ?, ?, 'Fornitore Manuale')", (p_id, lotto_id, qta_lotto_m, costo_t_m))
                    st.success("✅ Prodotto e lotto registrati!")
                    st.rerun()

# ------------------------------------------
# TAB 4: STATISTICHE CLIENTI & DEBITI
# ------------------------------------------
with tab4:
    st.subheader("📈 Statistiche Avanzate Clienti")
    movimenti_df = get_movimenti_dettagliati_df()
    
    if not movimenti_df.empty:
        clienti_debito = movimenti_df[(movimenti_df['tipo'] == 'VENDITA') & (movimenti_df['stato_pagamento'] == 'Dopo (Credito)')]
        if not clienti_debito.empty:
            debito_per_cliente = clienti_debito.groupby('cliente')['incasso'].sum().reset_index()
            st.markdown("##### 💳 Clienti con Debiti Attivi")
            for _, r_d in debito_per_cliente.iterrows():
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"**{r_d['cliente']}**: € {r_d['incasso']:,.2f}")
                if col_d2.button(f"Salda Debito", key=f"btn_s_{r_d['cliente']}"):
                    segna_debito_pagato(r_d['cliente'])
                    st.success("Debito saldato e incassato in cassa!")
                    st.rerun()

# ------------------------------------------
# TAB 5: REPORT STORICO & RESET GAME
# ------------------------------------------
with tab5:
    st.subheader("📜 Registro Storico Transazioni")
    movimenti_df = get_movimenti_dettagliati_df()
    if not movimenti_df.empty:
        st.dataframe(movimenti_df, use_container_width=True, hide_index=True)
        csv_data = movimenti_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica Report CSV", data=csv_data, file_name="report_storico.csv", mime="text/csv")
    
    st.markdown("---")
    
    with st.expander("⚠️ DANGER ZONE: Resetta Dati e Inizia Nuova Partita", expanded=False):
        st.error("Questa operazione cancellerà permanentemente tutto lo storico vendite, i clienti, i lotti e azzererà la tua partita riportandoti al Giorno 1 con €200.")
        conferma_reset = st.checkbox("Sono sicuro di voler piallare tutti i dati e ricominciare da capo.")
        
        if st.button("💥 RESETTA TUTTO E RICOMINCIA DA ZERO", use_container_width=True):
            if conferma_reset:
                reset_completo_nuova_partita()
                st.success("🎉 Reset eseguito! Benvenuto nella tua nuova partita.")
                st.rerun()
            else:
                st.warning("Spunta la casella di conferma qui sopra per poter procedere col reset.")
