import sqlite3
import base64
import os
from datetime import datetime, date, timedelta
import random
import time
import pandas as pd
import streamlit as st
import altair as alt

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="LaBzz - Gestione Magazzino & Vita Reale",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# FUNZIONE GENERAZIONE CODICE LOTTO
# ==========================================
def genera_codice_lotto_automatico(data_riferimento=None):
    if data_riferimento is None:
        data_riferimento = date.today()
    giorno = data_riferimento.strftime("%d").lstrip("0")
    MESE_INIZIALI = ['g', 'f', 'm', 'a', 'm', 'g', 'l', 'a', 's', 'o', 'n', 'd']
    iniziale_mese = MESE_INIZIALI[data_riferimento.month - 1]
    anno_2_cifre = data_riferimento.strftime("%y")
    return f"{giorno}{iniziale_mese}{anno_2_cifre}"

# ==========================================
# FUNZIONE CARICAMENTO VIDEO BASE64
# ==========================================
def get_video_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    return None

# ==========================================
# INIEZIONE CSS CUSTOM
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

    .alert-banner {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-left: 5px solid #38bdf8;
        padding: 14px 18px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    }
    .alert-banner.urgent {
        border-left-color: #ef4444;
        background: linear-gradient(135deg, #2b1619 0%, #110809 100%);
    }
    .alert-banner.fun {
        border-left-color: #2ed573;
        background: linear-gradient(135deg, #112b1c 0%, #08110a 100%);
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
        word-break: break-word !important;
    }

    h1 {
        letter-spacing: 1px;
        text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.6), 0 0 20px rgba(56, 189, 248, 0.35) !important;
    }

    h2, h3, h4 {
        color: #f1f5f9 !important;
        letter-spacing: 0.5px;
        text-shadow: 2px 2px 6px rgba(0, 0, 0, 0.5) !important;
    }

    .dashboard-grid {
        display: grid !important;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 12px !important;
        width: 100% !important;
        margin-bottom: 25px !important;
    }

    .custom-card {
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 14px 8px !important;
        box-shadow: 0 8px 25px -5px rgba(0, 0, 0, 0.5), 
                    inset 0 1px 1px 0 rgba(255, 255, 255, 0.1) !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }

    .card-label {
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        margin-bottom: 6px !important;
    }

    .card-value {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        color: #38bdf8 !important;
        text-shadow: 0 2px 6px rgba(56, 189, 248, 0.3);
    }

    div[data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 16px !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4) !important;
        margin-bottom: 18px !important;
        overflow: hidden !important;
    }

    div[data-testid="stExpander"] details summary {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
        font-size: 0.98rem !important;
        padding: 14px 16px !important;
    }

    div[data-testid="stExpanderDetails"] {
        padding: 16px !important;
        border-top: 1px solid rgba(255, 255, 255, 0.05) !important;
    }

    div[data-testid="stForm"] {
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 16px !important;
        padding: 20px !important;
        margin-bottom: 20px !important;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'Fredoka', sans-serif !important;
        background: rgba(15, 23, 42, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 14px !important;
        color: #94a3b8 !important;
        font-weight: 700 !important;
        padding: 10px 16px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }

    .stButton {
        display: flex !important;
        justify-content: center !important;
        margin: 0 !important;
    }

    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        font-family: 'Fredoka', sans-serif !important;
        font-weight: 600 !important;
        background-color: rgba(15, 23, 42, 0.8) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
    }

    div[data-testid="stDataFrame"] {
        font-family: 'Fredoka', sans-serif !important;
        background: rgba(15, 23, 42, 0.6) !important;
        border-radius: 14px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        overflow: hidden !important;
        margin-bottom: 25px !important;
    }
</style>
""", unsafe_allow_html=True)

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
        )
        """)
        
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
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        )
        """)

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
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_narrativi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            testo TEXT NOT NULL,
            data_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS impostazioni (
            chiave TEXT PRIMARY KEY,
            valore TEXT NOT NULL
        )
        """)
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('soglia_esaurimento', '10.0')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('bot_attivo', '0')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('giorni_simulati', '0')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('nome_protagonista', 'Hassan')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('ultima_vendita_id', '0')")

init_db()

def get_impostazione(chiave, default_val=""):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valore FROM impostazioni WHERE chiave = ?", (chiave,))
        row = cursor.fetchone()
        return row[0] if row else default_val

def set_impostazione(chiave, valore):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO impostazioni (chiave, valore) VALUES (?, ?)", (chiave, str(valore)))

def aggiungi_log_db(testo):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO log_narrativi (testo) VALUES (?)", (testo,))

def get_tutti_log_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT testo FROM log_narrativi ORDER BY id ASC")
        return [row[0] for row in cursor.fetchall()]

def reset_database_totale():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimenti")
        cursor.execute("DELETE FROM lotti")
        cursor.execute("DELETE FROM prodotti")
        cursor.execute("DELETE FROM clienti")
        cursor.execute("DELETE FROM log_narrativi")
    set_impostazione('bot_attivo', '0')
    set_impostazione('giorni_simulati', '0')
    set_impostazione('ultima_vendita_id', '0')
    p_name = get_impostazione('nome_protagonista', 'Hassan')
    aggiungi_log_db(f"🚀 Inizio della saga: {p_name} timbra il cartellino in fabbrica mentre progetta il suo alter ego underground.")

# ==========================================
# MOTORE DI SIMULAZIONE GIORNO PER GIORNO (LIVE)
# ==========================================
def esegui_singolo_giorno(giorno_idx, p_name):
    if giorno_idx >= 365:
        set_impostazione('bot_attivo', '0')
        return False

    data_corrente = (date.today() - timedelta(days=365)) + timedelta(days=giorno_idx)
    ts_giorno = datetime.combine(data_corrente, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        
        saga_pool = [
            f"🏭 [{data_corrente.strftime('%d %b')}] Fabbrica: {p_name} monta ante e cassetti pensando a pattern Acid da 180 BPM.",
            f"🚗 [{data_corrente.strftime('%d %b')}] Alfa Giulietta: {p_name} viaggia lungo i tornanti di collina tra lavoro e boschi.",
            f"🧠 [{data_corrente.strftime('%d %b')}] Studio session: {p_name} collega l'Elektron Digitakt per una sessione notturna.",
            f"📦 [{data_corrente.strftime('%d %b')}] Magazzino: {p_name} movimenta bancali di truciolato e pianifica i prossimi mix.",
            f"🌲 [{data_corrente.strftime('%d %b')}] Fitness: {p_name} si allena con la heavy rope nei boschi di collina."
        ]
        aggiungi_log_db(random.choice(saga_pool))

        if data_corrente.day == 1:
            stipendio_netto = random.uniform(1650.0, 1800.0)
            aggiungi_log_db(f"💶 STIPENDIO DI FABBRICA: Bonifico di € {stipendio_netto:,.2f} accreditato per {p_name}.")

        if data_corrente.month == 12 and data_corrente.day == 15:
            tredicesima = random.uniform(1650.0, 1800.0)
            aggiungi_log_db(f"🎄 TREDICESIMA: Arrivata la tredicesima di € {tredicesima:,.2f} per {p_name}.")

        cursor.execute("SELECT SUM(quantita_attuale) FROM lotti")
        giacenza_totale = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT SUM(ricavo_totale) FROM movimenti WHERE tipo = 'VENDITA'")
        incassi_totali = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT SUM(costo_totale) FROM movimenti WHERE tipo = 'CARICO'")
        costi_lotti = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT SUM(costo_totale) FROM movimenti WHERE tipo = 'XME'")
        costi_xme_tot = cursor.fetchone()[0] or 0.0

        cassa_attuale = 500.0 + incassi_totali - costi_lotti - costi_xme_tot

        if giacenza_totale < 10.0:
            cursor.execute("SELECT id FROM prodotti")
            prod_disponibili = [r[0] for r in cursor.fetchall()]
            if prod_disponibili:
                p_id_rif = random.choice(prod_disponibili)
                qta_lotto = 80.0
                costo_base_lotto = qta_lotto * 4.50
                if cassa_attuale >= costo_base_lotto:
                    spesa_lotto = costo_base_lotto
                    nota_rifornimento = "Rifornimento standard"
                else:
                    spesa_lotto = costo_base_lotto * 1.27
                    nota_rifornimento = "Rifornimento a debito"
                    aggiungi_log_db(f"💳 {p_name} a corto di cassa: scatta il rifornimento a debito (+27%).")

                costo_u = spesa_lotto / qta_lotto
                codice_l = genera_codice_lotto_automatico(data_corrente)
                cursor.execute("""
                    INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (p_id_rif, codice_l, qta_lotto, qta_lotto, costo_u, data_corrente, data_corrente))
                l_id_rif = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, cliente, pagamento, note, data) 
                    VALUES (?, ?, 'CARICO', ?, ?, ?, 'Fornitore', 'Subito', ?, ?)
                """, (p_id_rif, l_id_rif, qta_lotto, costo_u, spesa_lotto, nota_rifornimento, ts_giorno))

        is_weekend = data_corrente.weekday() >= 5
        cursor.execute("SELECT nome FROM clienti")
        clienti_disponibili = [r[0] for r in cursor.fetchall()]
        if not clienti_disponibili:
            clienti_disponibili = ["Anonimo"]

        cursor.execute("SELECT id FROM prodotti")
        prod_ids = [r[0] for r in cursor.fetchall()]

        if not is_weekend:
            num_clienti = random.choices([0, 1], weights=[60, 40])[0]
            for _ in range(num_clienti):
                if not prod_ids:
                    break
                p_id = random.choice(prod_ids)
                cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario, codice_lotto FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC LIMIT 1", (p_id,))
                lotto_attivo = cursor.fetchone()
                if lotto_attivo:
                    l_id, qta_disp, costo_u, cod_lotto = lotto_attivo
                    qta_vendita = min(qta_disp, random.choice([1.0, 2.0]))
                    if qta_vendita > 0:
                        prezzo_unitario = 10.0
                        ricavo_totale = qta_vendita * prezzo_unitario
                        costo_totale = qta_vendita * costo_u
                        margine = ricavo_totale - costo_totale
                        nuova_qta = qta_disp - qta_vendita
                        data_comp = data_corrente if nuova_qta == 0 else None

                        cursor.execute("UPDATE lotti SET quantita_attuale = ?, data_completamento = ? WHERE id = ?", (nuova_qta, data_comp, l_id))
                        cliente = random.choice(clienti_disponibili)
                        pagamento = "Subito" if random.random() < 0.70 else "Dopo (Credito)"
                        cursor.execute("""
                            INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note, data)
                            VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (p_id, l_id, qta_vendita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, f"Vendita Feriale Lotto {cod_lotto}", ts_giorno))
                        
                        aggiungi_log_db(f"🎉 VENDITA: {cliente} acquista {qta_vendita:,.1f} g per € {ricavo_totale:,.2f}.")
        else:
            num_clienti_weekend = random.choices([0, 1, 2], weights=[50, 35, 15])[0]
            for _ in range(num_clienti_weekend):
                if not prod_ids:
                    break
                p_id = random.choice(prod_ids)
                cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario, codice_lotto FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC LIMIT 1", (p_id,))
                lotto_attivo = cursor.fetchone()
                if lotto_attivo:
                    l_id, qta_disp, costo_u, cod_lotto = lotto_attivo
                    qta_vendita = min(qta_disp, 1.0)
                    if qta_vendita > 0:
                        prezzo_unitario = 40.0
                        ricavo_totale = qta_vendita * prezzo_unitario
                        costo_totale = 20.0
                        margine = ricavo_totale - costo_totale
                        nuova_qta = qta_disp - qta_vendita
                        data_comp = data_corrente if nuova_qta == 0 else None

                        cursor.execute("UPDATE lotti SET quantita_attuale = ?, data_completamento = ? WHERE id = ?", (nuova_qta, data_comp, l_id))
                        cliente = random.choice(clienti_disponibili)
                        pagamento = "Subito" if random.random() < 0.80 else "Dopo (Credito)"
                        cursor.execute("""
                            INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note, data)
                            VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (p_id, l_id, qta_vendita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, f"Weekend Club", ts_giorno))
                        
                        aggiungi_log_db(f"🔥 SERATA CLUB: {cliente} acquista {qta_vendita:,.1f} g per € {ricavo_totale:,.2f}.")

    return True

# Gestione avanzamento continuo se attivo
if get_impostazione('bot_attivo', '0') == '1':
    giorni_gia_simulati = int(get_impostazione('giorni_simulati', '0'))
    if giorni_gia_simulati < 365:
        p_name = get_impostazione('nome_protagonista', 'Hassan')
        esegui_singolo_giorno(giorni_gia_simulati, p_name)
        set_impostazione('giorni_simulati', str(giorni_gia_simulati + 1))

def get_soglia_esaurimento():
    return float(get_impostazione('soglia_esaurimento', '10.0'))

def set_soglia_esaurimento(valore):
    set_impostazione('soglia_esaurimento', str(valore))

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
            m.id, m.data, p.nome AS prodotto, COALESCE(l.codice_lotto, 'N/D - Lotto Rimosso') AS codice_lotto,
            m.tipo, m.quantita, 'g' AS unita_misura, m.prezzo_unitario, m.ricavo_totale, m.costo_totale, 
            m.margine, COALESCE(m.cliente, 'Anonimo') AS cliente, COALESCE(m.pagamento, 'Subito') AS pagamento,
            m.note, m.lotto_id
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        LEFT JOIN lotti l ON m.lotto_id = l.id
        ORDER BY m.data DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_clienti_registrati():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM clienti ORDER BY nome ASC")
        return [row[0] for row in cursor.fetchall()]

def aggiungi_cliente_se_nuovo(nome):
    if nome and nome.strip() != "":
        nome_pulito = nome.strip().capitalize()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO clienti (nome) VALUES (?)", (nome_pulito,))

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
        risultati.append({
            'prodotto_id': p_id, 'prodotto': prod['nome'], 'unita_misura': 'g',
            'qta_disponibile': qta_totale, 'scorta_minima_g': float(prod['scorta_minima_g']),
            'costo_medio_ponderato': costo_medio, 'valore_mercato_unitario': float(prod['valore_mercato_unitario']),
            'valore_totale_costo': valore_costo_totale, 'valore_totale_mercato': valore_mercato_totale,
            'qta_venduta': float(vendite['quantita'].sum()), 'incasso_totale': float(vendite['ricavo_totale'].sum()),
            'margine_totale': float(vendite['margine'].sum())
        })
    return pd.DataFrame(risultati)

def elimina_lotto_db(lotto_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE movimenti SET lotto_id = NULL WHERE lotto_id = ?", (lotto_id,))
        cursor.execute("DELETE FROM lotti WHERE id = ?", (lotto_id,))

def segna_debito_pagato(nome_cliente):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE movimenti SET pagamento = 'Subito' WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))

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
        st.title("LaBzz")

# BANNER POP-UP NARRATIVO IN CIMA
tutti_log = get_tutti_log_db()
if tutti_log:
    ultima_notif = tutti_log[-1]
    is_urgent = "⚠️" in ultima_notif or "debito" in ultima_notif.lower()
    is_fun = "🎉" in ultima_notif or "VENDITA" in ultima_notif or "SERATA" in ultima_notif or "STIPENDIO" in ultima_notif or "Inizio" in ultima_notif
    css_class = "alert-banner urgent" if is_urgent else ("alert-banner fun" if is_fun else "alert-banner")
    p_name_attivo = get_impostazione('nome_protagonista', 'Hassan')
    st.markdown(f'<div class="{css_class}">📖 <b>Cronaca della Storia ({p_name_attivo}):</b> {ultima_notif}</div>', unsafe_allow_html=True)

# 6 Tabs configurate
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💸 Cassa", 
    "📊 Dashboard", 
    "🚚 Rifornimenti",
    "📈 Statistiche",
    "📜 Report & Storico",
    "🤖 Bot Live"
])

with tab1:
    st.subheader("💸 Cassa Operativa")
    tipo_operazione = st.radio("Seleziona Tipo Registrazione", ["Vendita", "XME"], horizontal=True)
    prodotti_disp_df = get_prodotti_disponibili_df()
    
    if prodotti_disp_df.empty:
        st.warning("⚠️ Nessun prodotto disponibile con giacenza in magazzino. Avvia la simulazione dal tab Bot Live o aggiungi un lotto.")
    else:
        if tipo_operazione == "Vendita":
            prod_nome = st.selectbox("Seleziona Prodotto da Vendere", prodotti_disp_df['nome'].tolist())
            prod_row = prodotti_disp_df[prodotti_disp_df['nome'] == prod_nome].iloc[0]
            p_id = int(prod_row['id'])
            
            with get_connection() as conn:
                query_lotti = "SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC, id ASC"
                lotti_disponibili = pd.read_sql_query(query_lotti, conn, params=(p_id,))

            qta_tot_disp = float(lotti_disponibili['quantita_attuale'].sum()) if not lotti_disponibili.empty else 0.0
            
            if qta_tot_disp <= 0:
                st.error(f"⚠️ Nessuna scorta disponibile per {prod_nome}.")
            else:
                st.info(f"Disponibilità totale: {qta_tot_disp:,.1f} g")
                
                col1, col2 = st.columns(2)
                with col1:
                    quantita_vendita = st.number_input("Quantità", min_value=0.0, value=0.0, step=0.5, format="%.1f")
                    totale_incassato = st.number_input("Euro", min_value=0.0, value=0.0, step=1.0, format="%.2f")
                with col2:
                    prezzo_unitario_calc = (totale_incassato / quantita_vendita) if quantita_vendita > 0 else 0.0
                    st.metric("Prezzo al Grammo Calcolato", f"€ {prezzo_unitario_calc:,.2f} / g")
                    
                    clienti_esistenti = get_clienti_registrati()
                    input_cliente = st.text_input("Nome Cliente", value="", placeholder="Inizia a digitare il nome...")
                    
                    suggerimenti = []
                    if input_cliente.strip() != "":
                        suggerimenti = [c for c in clienti_esistenti if input_cliente.strip().lower() in c.lower()]
                    
                    cliente_selezionato_suggerito = None
                    if suggerimenti:
                        cliente_selezionato_suggerito = st.selectbox("Suggerimenti Cliente", ["-- Seleziona o Continua a Scrivere --"] + suggerimenti, key="select_suggerimento_cliente")

                st.markdown("##### Modalità Pagamento")
                tipo_pagamento = st.radio("Quando ricevi i soldi?", ["Subito", "Dopo (Credito)"], horizontal=True)

                if st.button("Conferma Vendita", key="btn_conferma_v"):
                    if cliente_selezionato_suggerito and cliente_selezionato_suggerito != "-- Seleziona o Continua a Scrivere --":
                        nome_finale_cliente = cliente_selezionato_suggerito
                    elif input_cliente.strip() != "":
                        nome_finale_cliente = input_cliente.strip().capitalize()
                    else:
                        nome_finale_cliente = "Anonimo"

                    if quantita_vendita <= 0:
                        st.error("Inserisci una quantità superiore a 0 g.")
                    elif totale_incassato <= 0:
                        st.error("Inserisci l'importo in Euro.")
                    elif quantita_vendita > qta_tot_disp:
                        st.error(f"Quantità inserita ({quantita_vendita:,.1f} g) superiore alla disponibilità ({qta_tot_disp:,.1f} g).")
                    else:
                        aggiungi_cliente_se_nuovo(nome_finale_cliente)

                        with get_connection() as conn:
                            cursor = conn.cursor()
                            qta_da_scaricare = float(quantita_vendita)
                            for _, lotto in lotti_disponibili.iterrows():
                                if qta_da_scaricare <= 0:
                                    break
                                l_id = int(lotto['id'])
                                qta_lotto_disp = float(lotto['quantita_attuale'])
                                costo_u_lotto = float(lotto['costo_acquisto_unitario'])
                                cod_lotto = lotto['codice_lotto']
                                
                                prelievo = min(qta_lotto_disp, qta_da_scaricare)
                                nuova_qta_lotto = qta_lotto_disp - prelievo
                                qta_da_scaricare -= prelievo
                                
                                costo_quota = prelievo * costo_u_lotto
                                ricavo_quota = prelievo * prezzo_unitario_calc
                                margine_quota = ricavo_quota - costo_quota
                                
                                if nuova_qta_lotto == 0:
                                    cursor.execute("UPDATE lotti SET quantita_attuale = 0, data_completamento = ? WHERE id = ?", (date.today(), l_id))
                                else:
                                    cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta_lotto, l_id))
                                
                                timestamp_attuale = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                cursor.execute("""
                                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note, data)
                                    VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (p_id, l_id, prelievo, prezzo_unitario_calc, ricavo_quota, costo_quota, margine_quota, nome_finale_cliente, tipo_pagamento, f"Lotto {cod_lotto}", timestamp_attuale))
                        
                        aggiungi_log_db(f"💰 VENDITA MANUALE: {nome_finale_cliente} ha acquistato per € {totale_incassato:,.2f}!")
                        st.success(f"✅ Vendita a '{nome_finale_cliente}' registrata (Pagamento: {tipo_pagamento})!")
                        st.rerun()

        elif tipo_operazione == "XME":
            lotti_df = get_lotti_attivi_df()
            if lotti_df.empty:
                st.error("Nessun lotto con giacenza disponibile per l'operazione XME.")
            else:
                with st.form("form_xme"):
                    st.markdown("##### Registra Uscita Personale (XME)")
                    opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                    lotto_selezionato_label = st.selectbox("Seleziona Lotto da Scaricare", list(opzioni_lotto.keys()))
                    lotto_id_scelto = opzioni_lotto[lotto_selezionato_label]
                    lotto_row = lotti_df[lotti_df['id'] == lotto_id_scelto].iloc[0]
                    
                    qta_xme = st.number_input("Quantità (g)", min_value=0.5, max_value=float(lotto_row['quantita_attuale']), value=10.0, step=0.5, format="%.1f")
                    motivo = st.text_input("Note XME", placeholder="Es. Uso personale, Test, Note varie")

                    if st.form_submit_button("Conferma Uscita XME"):
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            nuova_qta = float(lotto_row['quantita_attuale']) - qta_xme
                            costo_perdita = qta_xme * float(lotto_row['costo_acquisto_unitario'])
                            prod_tutti = get_prodotti_tutti_df()
                            p_id = int(prod_tutti[prod_tutti['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                            
                            if nuova_qta == 0:
                                cursor.execute("UPDATE lotti SET quantita_attuale = 0, data_completamento = ? WHERE id = ?", (date.today(), lotto_id_scelto))
                            else:
                                cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, lotto_id_scelto))
                                
                            timestamp_attuale = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            cursor.execute("""
                                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, margine, cliente, pagamento, note, data)
                                VALUES (?, ?, 'XME', ?, 0, ?, ?, 'XME', 'Subito', ?, ?)
                            """, (p_id, lotto_id_scelto, qta_xme, costo_perdita, -costo_perdita, f"XME: {motivo}", timestamp_attuale))
                        st.warning("Operazione XME registrata e sincronizzata col lotto!")
                        st.rerun()

with tab2:
    st.subheader("📊 Dashboard & Analytics (Business vs Stipendio)")
    df_stato_disp = calcola_stato_magazzino(solo_disponibili=True)
    movimenti_df = get_movimenti_dettagliati_df()

    if df_stato_disp.empty and movimenti_df.empty:
        st.info("Nessun dato di magazzino o movimento disponibile.")
    else:
        stipendi_totali_accumulati = 0.0
        for notizia in tutti_log:
            if "STIPENDIO DI FABBRICA" in notizia or "TREDICESIMA" in notizia:
                try:
                    parte_euro = notizia.split("€ ")[1].split(" ")[0].replace(".", "").replace(",", ".")
                    stipendi_totali_accumulati += float(parte_euro)
                except:
                    pass

        totale_grammi_disp = df_stato_disp['qta_disponibile'].sum() if not df_stato_disp.empty else 0
        incasso_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['ricavo_totale'].sum() if not movimenti_df.empty else 0
        costi_lotti_tot = movimenti_df[movimenti_df['tipo'] == 'CARICO']['costo_totale'].sum() if not movimenti_df.empty else 0
        costi_xme_tot = movimenti_df[movimenti_df['tipo'] == 'XME']['costo_totale'].sum() if not movimenti_df.empty else 0
        
        cassa_business = 500.0 + incasso_tot - costi_lotti_tot - costi_xme_tot
        margine_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['margine'].sum() if not movimenti_df.empty else 0
        crediti_aperti = movimenti_df[(movimenti_df['tipo'] == 'VENDITA') & (movimenti_df['pagamento'] == 'Dopo (Credito)')]['ricavo_totale'].sum() if not movimenti_df.empty else 0
        cassa_personale_totale = cassa_business + stipendi_totali_accumulati

        st.markdown("##### 💼 Flussi di Business (Magazzino & Vendite)")
        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="custom-card">
                <div class="card-label">Cassa Business Netta</div>
                <div class="card-value">€ {cassa_business:,.2f}</div>
            </div>
            <div class="custom-card">
                <div class="card-label">Incasso Totale Business</div>
                <div class="card-value">€ {incasso_tot:,.2f}</div>
            </div>
            <div class="custom-card">
                <div class="card-label">Margine Netto Reale</div>
                <div class="card-value">€ {margine_tot:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("##### 💶 Entrate Personali & Stipendio (Fabbrica)")
        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="custom-card">
                <div class="card-label">Stipendi Totali Accreditati</div>
                <div class="card-value" style="color: #38bdf8;">€ {stipendi_totali_accumulati:,.2f}</div>
            </div>
            <div class="custom-card">
                <div class="card-label">Crediti Aperti da Riscuotere</div>
                <div class="card-value" style="color: #ef4444;">€ {crediti_aperti:,.2f}</div>
            </div>
            <div class="custom-card">
                <div class="card-label">Patrimonio Totale (Stipendi + Business)</div>
                <div class="card-value" style="color: #2ed573;">€ {cassa_personale_totale:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown("##### 📦 Giacenze Attuali per Prodotto")
            if not df_stato_disp.empty:
                st.dataframe(df_stato_disp[['prodotto', 'qta_disponibile', 'valore_totale_mercato']], use_container_width=True, hide_index=True)
            else:
                st.info("Nessuna giacenza attiva.")
        with col_s2:
            st.markdown("##### 🔍 Panoramica Costi & Consumi")
            st.metric("Totale Speso in Rifornimenti (Lotti)", f"€ {costi_lotti_tot:,.2f}")
            st.metric("Totale Valore Uso Personale (XME)", f"€ {costi_xme_tot:,.2f}")
            st.metric("Giacenza Totale in Grammi", f"{totale_grammi_disp:,.1f} g")

        st.markdown("---")
        st.subheader("📈 Storico Progressivo Operazioni (Business)")
        if not movimenti_df.empty:
            mov_df = movimenti_df.copy()
            mov_df['Data_Ora'] = pd.to_datetime(mov_df['data'])
            mov_df = mov_df.sort_values('Data_Ora')
            mov_df['Spesi Totali'] = mov_df.apply(lambda r: r['costo_totale'] if r['tipo'] == 'CARICO' else 0, axis=1).cumsum()
            mov_df['Incasso Totale'] = mov_df['ricavo_totale'].cumsum()
            mov_df['Margine Netto'] = mov_df['margine'].cumsum()
            
            chart_df = mov_df.melt(
                id_vars=['Data_Ora', 'prodotto', 'tipo'],
                value_vars=['Spesi Totali', 'Incasso Totale', 'Margine Netto'],
                var_name='Metrica',
                value_name='Valore (€)'
            )
            chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Data_Ora:T', title='Data e Ora Transazione'),
                y=alt.Y('Valore (€):Q', title='Importo (€)'),
                color=alt.Color('Metrica:N', scale=alt.Scale(domain=['Spesi Totali', 'Incasso Totale', 'Margine Netto'], range=['#ff4757', '#2ed573', '#38bdf8']), legend=alt.Legend(title="Legenda")),
                tooltip=['Data_Ora:T', 'prodotto:N', 'tipo:N', 'Metrica:N', 'Valore (€):Q']
            ).properties(height=420).configure_view(strokeWidth=0).configure_axis(gridColor='rgba(255,255,255,0.05)', labelColor='#94a3b8', titleColor='#f8fafc').interactive()
            st.altair_chart(chart, use_container_width=True)

with tab3:
    st.subheader("🚚 Registro Rifornimenti e Lotti")
    soglia_attuale = get_soglia_esaurimento()
    report_lotti_df = get_report_lotti_integrato_df(soglia_esaurimento_g=soglia_attuale)
    
    if not report_lotti_df.empty:
        lotti_warning = report_lotti_df[report_lotti_df['stato_lotto'].str.contains("⚠️")]
        for _, w_row in lotti_warning.iterrows():
            st.warning(f"⚠️ Lotto {w_row['codice_lotto']} ({w_row['prodotto']}) in esaurimento! Scorta residua: {w_row['quantita_attuale']:,.1f} g")

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Costo Totale Acquisizione Lotti", f"€ {report_lotti_df['costo_totale_lotto'].sum():,.2f}")
        col_m2.metric("Incasso Totale Generato dai Lotti", f"€ {report_lotti_df['incasso_totale_lotto'].sum():,.2f}")
        col_m3.metric("Guadagno Netto Reale Lotti", f"€ {report_lotti_df['guadagno_netto_lotto'].sum():,.2f}")
        st.markdown("---")
        st.dataframe(report_lotti_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    col_cfg1, col_cfg2, col_cfg3 = st.columns([1, 2, 1])
    with col_cfg2:
        nuova_soglia = st.number_input("⚙️ Soglia Alert In Esaurimento (g)", min_value=1.0, value=soglia_attuale, step=1.0, format="%.1f")
        if nuova_soglia != soglia_attuale:
            set_soglia_esaurimento(nuova_soglia)
            st.success(f"Soglia salvata permanentemente a {nuova_soglia:,.1f} g!")
            st.rerun()

    st.markdown("---")
    with st.expander("➕ Aggiungi un Nuovo Prodotto e Rifornimento", expanded=False):
        with st.form("form_nuovo_prodotto_lotto"):
            nome_nuovo = st.text_input("Nome Prodotto", placeholder="Es. Hash / Amnesia Haze")
            data_acq_m = st.date_input("Data di Acquisto Lotto", value=date.today())
            cod_lotto_m = st.text_input("Codice Lotto", value=genera_codice_lotto_automatico(data_acq_m))
            qta_lotto_m = st.number_input("Quantità Lotto (g)", min_value=0.5, value=80.0, step=0.5, format="%.1f")
            costo_u_lotto_m = st.number_input("Costo Unitario d'Acquisto (€/g)", min_value=0.1, value=4.50, step=0.25, format="%.2f")
            prezzo_v_init = st.number_input("Prezzo di Vendita Standard (€/g)", min_value=0.1, value=10.0, step=0.5, format="%.2f")
            scorta_min_init = st.number_input("Scorta Minima Alert (g)", min_value=0.0, value=10.0, step=5.0, format="%.1f")

            if st.form_submit_button("Crea Prodotto e Registra Lotto"):
                if nome_nuovo.strip() == "":
                    st.error("Inserisci un nome valido per il prodotto.")
                else:
                    try:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO prodotti (nome, unita_misura, valore_mercato_unitario, scorta_minima_g) VALUES (?, 'g', ?, ?)", (nome_nuovo.strip(), prezzo_v_init, scorta_min_init))
                            p_id = cursor.lastrowid
                            cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, ?, ?, ?, ?, ?, ?)", (p_id, cod_lotto_m.strip(), qta_lotto_m, qta_lotto_m, costo_u_lotto_m, data_acq_m, date.today()))
                            lotto_id = cursor.lastrowid
                            timestamp_attuale = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, cliente, pagamento, note, data) VALUES (?, ?, 'CARICO', ?, ?, ?, 'Fornitore', 'Subito', 'Primo Carico Lotto', ?)", (p_id, lotto_id, qta_lotto_m, costo_u_lotto_m, qta_lotto_m * costo_u_lotto_m, timestamp_attuale))
                        st.success(f"✅ Prodotto '{nome_nuovo}' creato!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Un prodotto con questo nome esiste già.")

    with st.expander("➕ Aggiungi Lotto a Prodotto Esistente", expanded=False):
        prodotti_esistenti_df = get_prodotti_tutti_df()
        if not prodotti_esistenti_df.empty:
            with st.form("form_lotto_aggiuntivo"):
                p_nome_lotto = st.selectbox("Seleziona Prodotto Esistente", prodotti_esistenti_df['nome'].tolist())
                data_acq_add = st.date_input("Data di Acquisto", value=date.today(), key="date_acq_add")
                cod_lotto_add = st.text_input("Codice Lotto", value=genera_codice_lotto_automatico(data_acq_add), key="input_cod_lotto_add")
                qta_lotto_add = st.number_input("Quantità Lotto (g)", min_value=0.5, value=80.0, step=0.5, format="%.1f")
                costo_u_lotto_add = st.number_input("Costo Unitario d'Acquisto (€/g)", min_value=0.1, value=4.50, step=0.25, format="%.2f")
                
                if st.form_submit_button("➕ Aggiungi Nuovo Lotto"):
                    p_row_m = prodotti_esistenti_df[prodotti_esistenti_df['nome'] == p_nome_lotto].iloc[0]
                    p_id_m = int(p_row_m['id'])
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, ?, ?, ?, ?, ?, ?)", (p_id_m, cod_lotto_add.strip(), qta_lotto_add, qta_lotto_add, costo_u_lotto_add, data_acq_add, date.today()))
                        lotto_id = cursor.lastrowid
                        timestamp_attuale = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, cliente, pagamento, note, data) VALUES (?, ?, 'CARICO', ?, ?, ?, 'Fornitore', 'Subito', 'Rifornimento Lotto', ?)", (p_id_m, lotto_id, qta_lotto_add, costo_u_lotto_add, qta_lotto_add * costo_u_lotto_add, timestamp_attuale))
                    st.success("✅ Lotto aggiunto!")
                    st.rerun()

    with st.expander("🗑️ Rimuovi un Lotto Esistente", expanded=False):
        if not report_lotti_df.empty:
            opzioni_lotti_gest = {f"ID {r['lotto_id']} | {r['prodotto']} - {r['codice_lotto']} (Residuo: {r['quantita_attuale']:,.1f} g)": r['lotto_id'] for _, r in report_lotti_df.iterrows()}
            id_lotto_scelto = st.selectbox("Seleziona Lotto da Eliminare", list(opzioni_lotti_gest.keys()))
            if st.button("🗑️ Rimuovi Definitivamente Lotto"):
                elimina_lotto_db(opzioni_lotti_gest[id_lotto_scelto])
                st.success("Lotto rimosso!")
                st.rerun()

with tab4:
    st.subheader("📈 Statistiche Avanzate Clienti")
    movimenti_df = get_movimenti_dettagliati_df()
    vendite_df = movimenti_df[movimenti_df['tipo'] == 'VENDITA'].copy() if not movimenti_df.empty else pd.DataFrame()
    
    if "cliente_selezionato_debito" not in st.session_state:
        st.session_state["cliente_selezionato_debito"] = None

    if not movimenti_df.empty:
        clienti_debito = movimenti_df[(movimenti_df['tipo'] == 'VENDITA') & (movimenti_df['pagamento'] == 'Dopo (Credito)')]
        if not clienti_debito.empty:
            debito_per_cliente = clienti_debito.groupby('cliente')['ricavo_totale'].sum().reset_index()
            cols = st.columns(len(debito_per_cliente))
            for idx, row_d in debito_per_cliente.iterrows():
                c_nome = row_d['cliente']
                with cols[idx]:
                    if st.button(f"✨ {c_nome}", key=f"btn_nome_{c_nome}", use_container_width=True):
                        st.session_state["cliente_selezionato_debito"] = c_nome

            cli_selezionato = st.session_state["cliente_selezionato_debito"]
            if cli_selezionato:
                importo_selezionato = debito_per_cliente[debito_per_cliente['cliente'] == cli_selezionato]['ricavo_totale'].values
                if len(importo_selezionato) > 0:
                    importo_val = importo_selezionato[0]
                    with st.container(border=True):
                        st.markdown(f"### 💳 Gestione Debito: **{cli_selezionato}**")
                        st.markdown(f"**Importo da riscuotere:** <span style='color: #ef4444; font-size: 1.3rem;'>€ {importo_val:,.2f}</span>", unsafe_allow_html=True)
                        col_p1, col_p2 = st.columns(2)
                        with col_p1:
                            if st.button("✅ Conferma Pagamento", key=f"conferma_pag_{cli_selezionato}", use_container_width=True):
                                segna_debito_pagato(cli_selezionato)
                                st.session_state["cliente_selezionato_debito"] = None
                                st.success(f"Debito di {cli_selezionato} saldato con successo!")
                                st.rerun()
                        with col_p2:
                            if st.button("❌ Chiudi", key=f"chiudi_pop_{cli_selezionato}", use_container_width=True):
                                st.session_state["cliente_selezionato_debito"] = None
                                st.rerun()

    if movimenti_df.empty:
        st.info("Nessun movimento registrato per le statistiche temporali.")
    else:
        stat_df = movimenti_df.copy()
        stat_df['Data_Ora'] = pd.to_datetime(stat_df['data'])
        stat_df = stat_df.sort_values('Data_Ora')
        stat_df['Soldi Lotto (Blu)'] = stat_df.apply(lambda r: r['costo_totale'] if r['tipo'] == 'CARICO' else 0, axis=1).cumsum()
        stat_df['Soldi Guadagnati (Verde)'] = stat_df.apply(lambda r: r['ricavo_totale'] if r['tipo'] == 'VENDITA' and r['pagamento'] == 'Subito' else 0, axis=1).cumsum()
        stat_df['Soldi a Credito (Rosso)'] = stat_df.apply(lambda r: r['ricavo_totale'] if r['tipo'] == 'VENDITA' and r['pagamento'] == 'Dopo (Credito)' else 0, axis=1).cumsum()
        
        chart_stat_df = stat_df.melt(
            id_vars=['Data_Ora', 'prodotto', 'tipo'],
            value_vars=['Soldi Lotto (Blu)', 'Soldi Guadagnati (Verde)', 'Soldi a Credito (Rosso)'],
            var_name='Metrica',
            value_name='Importo (€)'
        )
        chart_temp = alt.Chart(chart_stat_df).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X('Data_Ora:T', title='Data e Ora'),
            y=alt.Y('Importo (€):Q', title='Importo (€)'),
            color=alt.Color('Metrica:N', scale=alt.Scale(domain=['Soldi Lotto (Blu)', 'Soldi Guadagnati (Verde)', 'Soldi a Credito (Rosso)'], range=['#38bdf8', '#2ed573', '#ff4757']), legend=alt.Legend(title="Legenda Finanziaria", orient="bottom")),
            tooltip=['Data_Ora:T', 'prodotto:N', 'tipo:N', 'Metrica:N', 'Importo (€):Q']
        ).properties(height=400).configure_view(strokeWidth=0).configure_axis(gridColor='rgba(255,255,255,0.05)', labelColor='#94a3b8', titleColor='#f8fafc').interactive()
        st.altair_chart(chart_temp, use_container_width=True)

with tab5:
    st.subheader("📜 Registro Storico Transazioni")
    movimenti_df = get_movimenti_dettagliati_df()
    if not movimenti_df.empty:
        st.dataframe(movimenti_df, use_container_width=True, hide_index=True)
        csv_data = movimenti_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica Report Storico in CSV", data=csv_data, file_name=f"report_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

with tab6:
    st.subheader("🤖 Bot Live: Pannello di Controllo")
    
    bot_attivo = get_impostazione('bot_attivo', '0') == '1'
    giorni_simulati_correnti = int(get_impostazione('giorni_simulati', '0'))
    p_name_corrente = get_impostazione('nome_protagonista', 'Hassan')

    if not bot_attivo:
        st.markdown("Avvia il bot per far partire il timer in tempo reale (1 giorno ogni 2 secondi) e vedere dashboard e grafici aggiornarsi giorno per giorno.")
        
        col_nome1, col_nome2 = st.columns([2, 1])
        with col_nome1:
            nuovo_nome = st.text_input("🏷️ Nome del Protagonista", value=p_name_corrente)
            if nuovo_nome.strip() != "" and nuovo_nome != p_name_corrente:
                set_impostazione('nome_protagonista', nuovo_nome.strip().capitalize())
                st.rerun()

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🚀 Avvia Bot Live", use_container_width=True):
                reset_database_totale()
                p_name = get_impostazione('nome_protagonista', 'Hassan')
                
                with get_connection() as conn:
                    cursor = conn.cursor()
                    prodotti_nomi = ["Hash", "Amnesia Haze", "Super Skunk"]
                    for p_nome in prodotti_nomi:
                        cursor.execute("INSERT OR IGNORE INTO prodotti (nome, unita_misura, valore_mercato_unitario, scorta_minima_g) VALUES (?, 'g', 15.0, 10.0)", (p_nome,))
                    clienti_fittizi = ["Mario Rossi", "Luca Bianchi", "Giulia Verdi", "Sara Neri", "Marco Gialli"]
                    for c in clienti_fittizi:
                        cursor.execute("INSERT OR IGNORE INTO clienti (nome) VALUES (?)", (c,))

                    data_inizio = date.today() - timedelta(days=365)
                    cursor.execute("SELECT id FROM prodotti WHERE nome = 'Hash'")
                    p_id_init = cursor.fetchone()[0]
                    qta_init = 80.0
                    costo_u_init = 4.50
                    costo_tot_init = qta_init * costo_u_init
                    codice_l_init = genera_codice_lotto_automatico(data_inizio)
                    
                    cursor.execute("""
                        INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (p_id_init, codice_l_init, qta_init, qta_init, costo_u_init, data_inizio, data_inizio))
                    l_id_init = cursor.lastrowid
                    ts_c = datetime.combine(data_inizio, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("""
                        INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, cliente, pagamento, note, data) 
                        VALUES (?, ?, 'CARICO', ?, ?, ?, 'Fornitore', 'Subito', ?, ?)
                    """, (p_id_init, l_id_init, qta_init, costo_u_init, costo_tot_init, f"Lotto Iniziale per {p_name}", ts_c))

                set_impostazione('bot_attivo', '1')
                set_impostazione('giorni_simulati', '0')
                st.success("✅ Bot avviato!")
                st.rerun()

        with col_b2:
            if st.button("🗑️ RESET TOTALE DATI", use_container_width=True):
                reset_database_totale()
                st.success("✅ Reset generale completato con successo!")
                st.rerun()

    else:
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            st.markdown(f"🟢 **Bot Live in esecuzione ({p_name_corrente})**")
        with col_t2:
            st.markdown(f"⏳ **Giorno {giorni_simulati_correnti} / 365**")

        st.progress(min(giorni_simulati_correnti / 365.0, 1.0))
        
        if st.button("⏹️ Ferma il Bot", use_container_width=True):
            set_impostazione('bot_attivo', '0')
            st.warning("🛑 Bot arrestato.")
            st.rerun()

        if giorni_simulati_correnti < 365:
            time.sleep(2)  # Pausa di 2 secondi prima del prossimo giorno
            st.rerun()