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

def set_soglia_esaurimento(valore):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE impostazioni SET valore = ? WHERE chiave = 'soglia_esaurimento'", (valore,))

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
            COALESCE(l.codice_lotto, 'N/D - Lotto Rimosso') AS codice_lotto,
            m.tipo, 
            m.quantita, 
            'g' AS unita_misura,
            m.prezzo_unitario, 
            m.ricavo_totale, 
            m.costo_totale, 
            m.margine, 
            COALESCE(m.cliente, 'Anonimo') AS cliente,
            COALESCE(m.pagamento, 'Subito') AS pagamento,
            m.note, 
            m.lotto_id
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
        cursor.execute("UPDATE movimenti SET pagamento = 'Subito' WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))

def elimina_lotto_db(lotto_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE movimenti SET lotto_id = NULL WHERE lotto_id = ?", (lotto_id,))
        cursor.execute("DELETE FROM lotti WHERE id = ?", (lotto_id,))

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
# GENERAZIONE OFFERTE & CLIENTE ATTUALE IN NEGOZIO
# ==========================================
def genera_offerta_fornitore_casuale():
    prodotti_df = get_prodotti_tutti_df()
    if not prodotti_df.empty:
        prod_row = prodotti_df.sample(n=1).iloc[0]
        p_id = int(prod_row['id'])
        p_nome = prod_row['nome']
        
        roll_tipo = random.random()
        
        if roll_tipo < 0.10:
            qta = float(random.choice([200, 300, 500]))
            costo_u = round(random.uniform(2.80, 3.40), 2)
            tipo_offerta = "🔥 Sottocosto Raro (Standard Base)"
            valore_mercato_suggerito = 5.00
        elif roll_tipo < 0.30:
            qta = float(random.choice([200, 300, 400]))
            costo_u = round(random.uniform(6.50, 9.00), 2)
            tipo_offerta = "💎 Special Top Quality (Vendita ad Alto Margine)"
            valore_mercato_suggerito = costo_u * 1.6
        elif roll_tipo < 0.70:
            qta = float(random.choice([200, 300, 500]))
            costo_u = round(random.uniform(3.50, 4.50), 2)
            tipo_offerta = "📦 Stock Volume (>2 etti)"
            valore_mercato_suggerito = 6.00
        else:
            qta = 100.0
            costo_u = round(random.uniform(4.50, 6.00), 2)
            tipo_offerta = "🏷️ Singolo Etto (100g Standard)"
            valore_mercato_suggerito = 7.50

        st.session_state.offerta_fornitore = {
            "prodotto_id": p_id,
            "prodotto_nome": p_nome,
            "quantita": qta,
            "costo_unitario": costo_u,
            "costo_totale": qta * costo_u,
            "valore_mercato_suggerito": valore_mercato_suggerito,
            "tipo": tipo_offerta,
            "codice_lotto": f"OFF-{random.randint(100,999)}"
        }

def genera_cliente_in_negozio():
    prod_disp = get_prodotti_disponibili_df()
    if not prod_disp.empty:
        prod = prod_disp.sample(n=1).iloc[0]
        nomi_clienti = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "ClienteVIP", "Matteo", "Valentina"]
        nome_c = random.choice(nomi_clienti)
        qta_req = float(random.choice([5, 10, 15, 20, 30]))
        budget_u = float(prod['valore_mercato_unitario']) * random.uniform(0.85, 1.35)
        
        st.session_state.cliente_in_negozio = {
            "nome": nome_c,
            "prodotto_id": int(prod['id']),
            "prodotto_nome": prod['nome'],
            "quantita_richiesta": qta_req,
            "budget_max_g": round(budget_u, 2)
        }
    else:
        st.session_state.cliente_in_negozio = None

def verifica_arrivo_offerta_dinamica():
    if st.session_state.offerta_fornitore is not None:
        return

    df_disp = calcola_stato_magazzino(solo_disponibili=True)
    scorta_totale = df_disp['qta_disponibile'].sum() if not df_disp.empty else 0
    soglia_alert = get_soglia_esaurimento()

    probabilita = 0.80 if scorta_totale <= soglia_alert else 0.22

    if random.random() < probabilita:
        genera_offerta_fornitore_casuale()
        aggiungi_log("📨 Un fornitore ti ha inviato una nuova proposta di stock!")

if 'energia' not in st.session_state:
    st.session_state.energia = 100
if 'giorno' not in st.session_state:
    st.session_state.giorno = 1
if 'reputazione' not in st.session_state:
    st.session_state.reputazione = 50
if 'fedelta_clienti' not in st.session_state:
    st.session_state.fedelta_clienti = 10
if 'log_gioco' not in st.session_state:
    st.session_state.log_gioco = ["🎮 Benvenuto! Il sistema gestionale e Tycoon è attivo."]
if 'offerta_fornitore' not in st.session_state:
    st.session_state.offerta_fornitore = None
if 'cliente_in_negozio' not in st.session_state:
    st.session_state.cliente_in_negozio = None

if st.session_state.cliente_in_negozio is None:
    genera_cliente_in_negozio()

if st.session_state.giorno == 1 and st.session_state.offerta_fornitore is None:
    genera_offerta_fornitore_casuale()

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
        
        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario, scorta_minima_g) VALUES ('Varietà Iniziale', 6.0, 20.0);")
        p_id = cursor.lastrowid
        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, 'START-01', 200.0, 200.0, 4.0, ?, ?);", (p_id, date.today(), date.today()))
        l_id = cursor.lastrowid
        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', 200.0, 800.0, 'Fornitore Iniziale', 'Capitale di partenza')", (p_id, l_id))
    
    st.session_state.giorno = 1
    st.session_state.energia = 100
    st.session_state.reputazione = 50
    st.session_state.fedelta_clienti = 10
    st.session_state.log_gioco = ["✨ Nuova Avventura Iniziata! Tutti i dati sono stati resettati a zero."]
    st.session_state.offerta_fornitore = None
    st.session_state.cliente_in_negozio = None
    genera_offerta_fornitore_casuale()
    genera_cliente_in_negozio()

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
        border-radius: 16px !important;
        padding: 14px 8px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
    }

    .card-label {
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        margin-bottom: 6px !important;
    }

    .card-value {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        color: #38bdf8 !important;
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

# HEADER METRICHE TYCOON GIOCATORE
c_g1, c_g2, c_g3, c_g4 = st.columns(4)
c_g1.metric("📅 Turno / Giorno", f"Giorno {st.session_state.giorno}")
c_g2.metric("⚡ Energia Imprenditore", f"{st.session_state.energia}%")
c_g3.metric("⭐ Reputazione", f"{st.session_state.reputazione}/100")
c_g4.metric("❤️ Fedeltà Clienti", f"{st.session_state.fedelta_clienti}%")

st.markdown("---")

# ==========================================
# SCHEDE / TAB DELL'APPLICAZIONE
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💸 Cassa", 
    "📊 Dashboard", 
    "🚚 Rifornimenti",
    "📈 Statistiche",
    "📜 Report & Storico"
])

# ------------------------------------------
# TAB 1: CASSA OPERATIVA (INTERATTIVA)
# ------------------------------------------
with tab1:
    st.subheader("💸 Cassa Operativa & Modalità Vendita")
    
    col_t1, col_t2 = st.columns([2, 1])
    
    with col_t1:
        tipo_operazione = st.radio("Seleziona Tipo Registrazione", ["Incontra Cliente (Manuale)", "Automazione Turno AI", "XME (Perk)"], horizontal=True)
        prodotti_disp_df = get_prodotti_disponibili_df()
        
        if prodotti_disp_df.empty:
            st.warning("⚠️ Nessun prodotto disponibile in magazzino. Aggiungi un lotto dalla scheda 'Rifornimenti'.")
        else:
            if tipo_operazione == "Incontra Cliente (Manuale)":
                st.markdown("##### 👤 Cliente Attualmente alla Cassa")
                
                cli_att = st.session_state.cliente_in_negozio
                if cli_att:
                    with st.container(border=True):
                        st.markdown(f"### **{cli_att['nome']}** è qui per comprare!")
                        st.write(f"• **Richiesta:** {cli_att['quantita_richiesta']} g di *{cli_att['prodotto_nome']}*")
                        
                        with get_connection() as conn:
                            lotti_disp = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(cli_att['prodotto_id'],)).iloc[0, 0]
                        qta_disp_tot = float(lotti_disp) if lotti_disp else 0.0

                        if qta_disp_tot < cli_att['quantita_richiesta']:
                            st.error(f"⚠️ Non hai abbastanza scorte! Servono {cli_att['quantita_richiesta']}g ma ne hai solo {qta_disp_tot:.1f}g.")
                        else:
                            st.info(f"Disponibilità in magazzino: {qta_disp_tot:.1f} g")
                            
                            col_p1, col_p2 = st.columns(2)
                            with col_p1:
                                prezzo_proposto = st.number_input("Imposta il Tuo Prezzo al Grammo (€/g)", min_value=0.5, value=6.0, step=0.5, format="%.2f")
                                totale_proposto = prezzo_proposto * cli_att['quantita_richiesta']
                                st.write(f"**Totale Incasso Proposto:** € {totale_proposto:.2f}")

                            tipo_pagamento = st.radio("Modalità Pagamento", ["Subito", "Dopo (Credito)"], horizontal=True)

                            col_act1, col_act2 = st.columns(2)
                            with col_act1:
                                if st.button("🤝 Proponi Offerta e Vendi"):
                                    # Verifica se il prezzo proposto supera la tolleranza del cliente
                                    if prezzo_proposto <= cli_att['budget_max_g']:
                                        aggiungi_cliente_se_nuovo(cli_att['nome'])
                                        with get_connection() as conn:
                                            cursor = conn.cursor()
                                            lotti_df = pd.read_sql_query("SELECT id, quantita_attuale, costo_acquisto_unitario, codice_lotto FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", conn, params=(cli_att['prodotto_id'],))
                                            
                                            qta_da_scaricare = cli_att['quantita_richiesta']
                                            for _, lotto in lotti_df.iterrows():
                                                if qta_da_scaricare <= 0: break
                                                l_id = int(lotto['id'])
                                                qta_lotto_disp = float(lotto['quantita_attuale'])
                                                prelievo = min(qta_lotto_disp, qta_da_scaricare)
                                                nuova_qta = qta_lotto_disp - prelievo
                                                qta_da_scaricare -= prelievo
                                                
                                                ricavo_q = prelievo * prezzo_proposto
                                                costo_q = prelievo * float(lotto['costo_acquisto_unitario'])
                                                margine_q = ricavo_q - costo_q
                                                
                                                if nuova_qta == 0:
                                                    cursor.execute("UPDATE lotti SET quantita_attuale = 0, data_completamento = ? WHERE id = ?", (date.today(), l_id))
                                                else:
                                                    cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, l_id))
                                                
                                                cursor.execute("""
                                                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note)
                                                    VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?)
                                                """, (cli_att['prodotto_id'], l_id, prelievo, prezzo_proposto, ricavo_q, costo_q, margine_q, cli_att['nome'], tipo_pagamento, f"Lotto {lotto['codice_lotto']}"))

                                        st.session_state.energia = max(0, st.session_state.energia - 10)
                                        st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 3)
                                        spara_fuochi_d_artificio()
                                        st.success(f"🎉 {cli_att['nome']} ha ACCETTATO! Incassati € {totale_proposto:.2f}")
                                        genera_cliente_in_negozio()
                                        st.rerun()
                                    else:
                                        st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 2)
                                        st.error(f"❌ {cli_att['nome']} ritiene che €{prezzo_proposto:.2f}/g sia troppo caro e se n'è andato!")
                                        genera_cliente_in_negozio()
                                        st.rerun()

                            with col_act2:
                                if st.button("🚪 Rifiuta / Prossimo Cliente"):
                                    st.info("Cliente congedato.")
                                    genera_cliente_in_negozio()
                                    st.rerun()

            elif tipo_operazione == "Automazione Turno AI":
                st.markdown("##### 🏪 Automazione Sales Engine (Istruisci il Bot di Vendita)")
                
                prod_target = st.selectbox("Seleziona Prodotto da Vendere nel Turno", prodotti_disp_df['nome'].tolist(), key="select_prod_target")
                p_target_row = prodotti_disp_df[prodotti_disp_df['nome'] == prod_target].iloc[0]
                p_target_id = int(p_target_row['id'])
                val_mercato_ref = float(p_target_row['valore_mercato_unitario'])
                
                prezzo_target_bot = st.number_input("Prezzo al Grammo Desiderato per il Bot (€/g)", min_value=0.1, value=val_mercato_ref, step=0.2, format="%.2f")
                
                if prezzo_target_bot > val_mercato_ref * 1.3:
                    st.warning("⚠️ Il prezzo impostato è MOLTO ALTO rispetto al valore di mercato. Molti clienti potrebbero rifiutare l'offerta!")
                elif prezzo_target_bot < val_mercato_ref * 0.9:
                    st.info("💡 Prezzo conveniente! I clienti accetteranno volentieri e aumenterà la loro fedeltà.")

                if st.button("🚀 Avvia Automazione Turno (-20% Energia)"):
                    if st.session_state.energia < 20:
                        st.error("Sei troppo stanco! Esegui un'uscita XME o riposa.")
                    else:
                        st.session_state.energia -= 20
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            
                            num_clienti_base = random.randint(2, 5)
                            bonus_clienti_fedeli = int(st.session_state.fedelta_clienti / 20)
                            num_clienti_tot = num_clienti_base + bonus_clienti_fedeli
                            
                            clienti_nomi = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "ClienteVIP", "Matteo"]
                            vendite_accettate = 0
                            
                            for _ in range(num_clienti_tot):
                                cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", (p_target_id,))
                                lotti = cursor.fetchall()
                                if not lotti: 
                                    aggiungi_log("Scorte esaurite durante il turno!")
                                    break
                                
                                cli = random.choice(clienti_nomi)
                                tolleranza_cliente = val_mercato_ref * random.uniform(0.85, 1.35) * (1 + (st.session_state.fedelta_clienti / 200))
                                
                                if prezzo_target_bot <= tolleranza_cliente:
                                    qta = min(lotti[0][1], float(random.choice([5, 10, 20, 30])))
                                    if qta <= 0: continue
                                    
                                    l_id, l_qta, l_costo = lotti[0]
                                    cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale - ? WHERE id = ?", (qta, l_id))
                                    ricavo = qta * prezzo_target_bot
                                    margine = ricavo - (qta * l_costo)
                                    
                                    cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento) VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, 'Subito')", (p_target_id, l_id, qta, prezzo_target_bot, ricavo, qta * l_costo, margine, cli))
                                    vendite_accettate += 1
                                    aggiungi_log(f"✅ {cli} ha ACCETTATO: comprati {qta}g per €{ricavo:.2f}")
                                else:
                                    aggiungi_log(f"❌ {cli} ha RIFIUTATO: prezzo €{prezzo_target_bot:.2f}/g ritenuto troppo alto.")

                        if vendite_accettate > (num_clienti_tot / 2):
                            st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 5)
                            st.session_state.reputazione = min(100, st.session_state.reputazione + 2)
                            st.success(f"Turno completato! Accettate {vendite_accettate} vendite su {num_clienti_tot} clienti. Fedeltà Clienti +5%!")
                        else:
                            st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 3)
                            st.warning(f"Turno fiacco: Solo {vendite_accettate} su {num_clienti_tot} clienti hanno acquistato. Rivedi i prezzi!")
                        
                        st.rerun()

            elif tipo_operazione == "XME":
                st.markdown("##### 🧪 Registra Uso Personale XME (+30% Energia)")
                lotti_df = get_lotti_attivi_df()
                if not lotti_df.empty:
                    with st.form("form_xme"):
                        opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                        lotto_sel = st.selectbox("Seleziona Lotto", list(opzioni_lotto.keys()))
                        lotto_id = opzioni_lotto[lotto_sel]
                        qta_xme = st.number_input("Quantità (g)", min_value=0.5, value=10.0, step=0.5)

                        if st.form_submit_button("Conferma Uscita XME"):
                            lotto_row = lotti_df[lotti_df['id'] == lotto_id].iloc[0]
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                nuova_q = float(lotto_row['quantita_attuale']) - qta_xme
                                p_id = int(get_prodotti_tutti_df()[get_prodotti_tutti_df()['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                                cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_q, lotto_id))
                                cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, margine, cliente, note) VALUES (?, ?, 'XME', ?, ?, ?, 'XME', 'Consumo Perk')", (p_id, lotto_id, qta_xme, qta_xme * float(lotto_row['costo_acquisto_unitario']), -qta_xme * float(lotto_row['costo_acquisto_unitario'])))
                            
                            st.session_state.energia = min(100, st.session_state.energia + 30)
                            st.warning("Uscita XME registrata! Energia aumentata (+30%).")
                            st.rerun()

    with col_t2:
        st.markdown("### 💤 Turno Notturno")
        if st.button("🌙 Riposa e Passa al Giorno Successivo", use_container_width=True):
            st.session_state.giorno += 1
            st.session_state.energia = 100
            verifica_arrivo_offerta_dinamica()
            genera_cliente_in_negozio()
            aggiungi_log(f"🌙 Giorno {st.session_state.giorno} iniziato. Energia al 100%.")
            st.rerun()

        st.markdown("---")
        st.markdown("##### 📜 Log Eventi Live")
        for log in st.session_state.log_gioco[:6]:
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
        incasso_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['ricavo_totale'].sum() if not movimenti_df.empty else 0
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
            mov_df['Spesi Totali'] = mov_df.apply(lambda r: r['costo_totale'] if r['tipo'] == 'CARICO' else 0, axis=1).cumsum()
            mov_df['Incasso Totale'] = mov_df['ricavo_totale'].cumsum()
            mov_df['Margine Netto'] = mov_df['margine'].cumsum()
            
            chart_df = mov_df.melt(id_vars=['Data_Ora', 'prodotto', 'tipo'], value_vars=['Spesi Totali', 'Incasso Totale', 'Margine Netto'], var_name='Metrica', value_name='Valore (€)')
            chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Data_Ora:T', title='Data e Ora'), y=alt.Y('Valore (€):Q', title='Importo (€)'),
                color=alt.Color('Metrica:N', scale=alt.Scale(domain=['Spesi Totali', 'Incasso Totale', 'Margine Netto'], range=['#ff4757', '#2ed573', '#38bdf8']))
            ).properties(height=350).interactive()
            st.altair_chart(chart, use_container_width=True)

# ------------------------------------------
# TAB 3: RIFORNIMENTI, OFFERTE & LOTTI
# ------------------------------------------
with tab3:
    st.subheader("🚚 Registro Rifornimenti e Gestione Offerte")
    
    if st.session_state.offerta_fornitore:
        off = st.session_state.offerta_fornitore
        with st.container(border=True):
            st.markdown(f"### 📨 Nuova Offerta In Arrivo dal Fornitore!")
            st.markdown(f"**Tipologia:** {off['tipo']}")
            col_off1, col_off2, col_off3 = st.columns(3)
            col_off1.write(f"**Prodotto:** {off['prodotto_nome']}")
            col_off2.write(f"**Quantità Proposta:** {off['quantita']:,.1f} g")
            col_off3.write(f"**Costo Unitario:** € {off['costo_unitario']:.2f} / g (Totale: € {off['costo_totale']:,.2f})")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("✅ ACCETTA OFFERTA LOTTO", use_container_width=True):
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (off['prodotto_id'], off['codice_lotto'], off['quantita'], off['quantita'], off['costo_unitario'], date.today(), date.today()))
                        l_id = cursor.lastrowid
                        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', ?, ?, 'Fornitore Offerta', 'Acquisto da Offerta')", (off['prodotto_id'], l_id, off['quantita'], off['costo_totale']))
                        cursor.execute("UPDATE prodotti SET valore_mercato_unitario = ? WHERE id = ?", (off['valore_mercato_suggerito'], off['prodotto_id']))

                    st.success(f"✅ Offerta accettata! Lotto {off['codice_lotto']} aggiunto al magazzino.")
                    st.session_state.offerta_fornitore = None
                    st.rerun()
            with col_b2:
                if st.button("❌ RIFIUTA OFFERTA", use_container_width=True):
                    st.info("Offerta rifiutata e scartata.")
                    st.session_state.offerta_fornitore = None
                    st.rerun()
    else:
        st.info("ℹ️ Nessuna offerta attiva al momento. I fornitori ti contatteranno periodicamente o quando le tue scorte saranno basse.")

    st.markdown("---")
    soglia_attuale = get_soglia_esaurimento()
    report_lotti_df = get_report_lotti_integrato_df(soglia_esaurimento_g=soglia_attuale)
    
    if not report_lotti_df.empty:
        st.dataframe(report_lotti_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    with st.expander("➕ Aggiungi Nuovo Prodotto e Rifornimento Standard"):
        with st.form("form_nuovo_prodotto_lotto"):
            nome_nuovo = st.text_input("Nome Prodotto")
            data_acq_m = st.date_input("Data Acquisto", value=date.today())
            cod_lotto_m = st.text_input("Codice Lotto", value=genera_codice_lotto_automatico(data_acq_m))
            qta_lotto_m = st.number_input("Quantità (g)", value=200.0)
            costo_u_lotto_m = st.number_input("Costo d'Acquisto (€/g)", value=4.0)
            prezzo_v_init = st.number_input("Prezzo Vendita (€/g)", value=6.0)

            if st.form_submit_button("Crea Prodotto e Registra Lotto"):
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (nome_nuovo.strip(), prezzo_v_init))
                    p_id = cursor.lastrowid
                    cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, ?, ?, ?, ?, ?, ?)", (p_id, cod_lotto_m.strip(), qta_lotto_m, qta_lotto_m, costo_u_lotto_m, data_acq_m, date.today()))
                    lotto_id = cursor.lastrowid
                    cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente) VALUES (?, ?, 'CARICO', ?, ?, 'Fornitore')", (p_id, lotto_id, qta_lotto_m, qta_lotto_m * costo_u_lotto_m))
                st.success("✅ Prodotto creato con successo!")
                st.rerun()

# ------------------------------------------
# TAB 4: STATISTICHE CLIENTI & DEBITI
# ------------------------------------------
with tab4:
    st.subheader("📈 Statistiche Avanzate Clienti")
    movimenti_df = get_movimenti_dettagliati_df()
    
    if not movimenti_df.empty:
        clienti_debito = movimenti_df[(movimenti_df['tipo'] == 'VENDITA') & (movimenti_df['pagamento'] == 'Dopo (Credito)')]
        if not clienti_debito.empty:
            debito_per_cliente = clienti_debito.groupby('cliente')['ricavo_totale'].sum().reset_index()
            st.markdown("##### 💳 Clienti con Debiti Attivi")
            for _, r_d in debito_per_cliente.iterrows():
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"**{r_d['cliente']}**: € {r_d['ricavo_totale']:,.2f}")
                if col_d2.button(f"Salda Debito", key=f"btn_s_{r_d['cliente']}"):
                    segna_debito_pagato(r_d['cliente'])
                    st.success("Debito saldato!")
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
        st.error("Questa operazione cancellerà permanentemente tutto lo storico vendite, i clienti, i lotti e azzererà la tua partita riportandoti al Giorno 1.")
        conferma_reset = st.checkbox("Sono sicuro di voler piallare tutti i dati e ricominciare da capo.")
        
        if st.button("💥 RESETTA TUTTO E RICOMINCIA DA ZERO", use_container_width=True):
            if conferma_reset:
                reset_completo_nuova_partita()
                st.success("🎉 Reset eseguito! Benvenuto nella tua nuova partita.")
                st.rerun()
            else:
                st.warning("Spunta la casella di conferma qui sopra per poter procedere col reset.")
