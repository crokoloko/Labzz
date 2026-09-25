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
    page_title="LaBzz - Idle Business RPG",
    page_icon="🕹️",
    layout="wide"
)

def genera_codice_lotto_automatico(data_riferimento=None):
    if data_riferimento is None:
        data_riferimento = date.today()
    giorno = data_riferimento.strftime("%d").lstrip("0")
    MESE_INIZIALI = ['g', 'f', 'm', 'a', 'm', 'g', 'l', 'a', 's', 'o', 'n', 'd']
    iniziale_mese = MESE_INIZIALI[data_riferimento.month - 1]
    anno_2_cifre = data_riferimento.strftime("%y")
    return f"{giorno}{iniziale_mese}{anno_2_cifre}"

# ==========================================
# INIEZIONE CSS CUSTOM (STILE VIDEOGIOCO ARCADE)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Titan+One&display=swap');

    .stApp {
        background-color: #060913 !important;
        background: linear-gradient(180deg, #04060b 0%, #060913 50%, #0b1021 100%) !important;
        color: #f8fafc !important;
        font-family: 'Fredoka', sans-serif !important;
        font-weight: 500;
    }

    header[data-testid="stHeader"] {
        display: none !important;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    .game-hud {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        background: rgba(15, 23, 42, 0.85);
        border: 2px solid rgba(56, 189, 248, 0.3);
        border-radius: 16px;
        padding: 14px;
        margin-bottom: 20px;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.6);
        text-align: center;
    }

    .hud-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .hud-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        color: #94a3b8;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    .hud-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: #38bdf8;
        text-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
    }

    .alert-banner {
        background: linear-gradient(135deg, #064e3b 0%, #022c22 100%);
        border-left: 5px solid #10b981;
        padding: 12px 16px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        font-size: 0.95rem;
    }

    h1, h2, h3, h4 {
        font-family: 'Titan One', cursive, sans-serif !important;
        color: #ffffff !important;
        text-align: center !important;
        letter-spacing: 1px;
        text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.7);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: transparent !important;
        justify-content: center !important;
        flex-wrap: wrap !important;
        margin-bottom: 15px !important;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'Fredoka', sans-serif !important;
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        color: #94a3b8 !important;
        font-weight: 700 !important;
        padding: 8px 14px !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(56, 189, 248, 0.5) !important;
        box-shadow: 0 0 15px rgba(37, 99, 235, 0.4);
    }

    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(15, 23, 42, 0.9) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px !important;
        font-family: 'Fredoka', sans-serif !important;
    }
</style>
""", unsafe_allow_html=True)

DB_NAME = "magazzino.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

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
        
        # Tabella clienti corretta con la colonna 'fiducia'
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            fiducia INTEGER DEFAULT 50
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
        CREATE TABLE IF NOT EXISTS upgrades (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            livello INTEGER DEFAULT 0,
            costo_base REAL NOT NULL,
            moltiplicatore_costo REAL DEFAULT 1.5,
            descrizione TEXT
        )
        """)
        
        upgrades_iniziali = [
            ("sconto_fornitore", "Sconti Fornitore Ingrosso", 0, 150.0, 1.6, "Riduce il costo di acquisto dei lotti del 10% per livello."),
            ("prezzo_vendita", "Marketing & Hype Club", 0, 200.0, 1.7, "Aumenta il prezzo di vendita del 15% per livello."),
            ("velocita_bot", "Automazione Bot Telegram", 0, 300.0, 2.0, "Aumenta la frequenza e la quantità delle vendite automatiche.")
        ]
        for up_id, up_nome, up_lvl, up_costo, up_molt, up_desc in upgrades_iniziali:
            cursor.execute("""
                INSERT OR IGNORE INTO upgrades (id, nome, livello, costo_base, moltiplicatore_costo, descrizione) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (up_id, up_nome, up_lvl, up_costo, up_molt, up_desc))

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS impostazioni (
            chiave TEXT PRIMARY KEY,
            valore TEXT NOT NULL
        )
        """)
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('simulazione_eseguita', '0')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('nome_protagonista', 'Hassan')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('energia', '100')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('stress', '15')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('log_strategico_finale', '')")

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

def aggiungi_log_db(cursor, testo):
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
        cursor.execute("UPDATE upgrades SET livello = 0")
    set_impostazione('simulazione_eseguita', '0')
    set_impostazione('log_strategico_finale', '')
    set_impostazione('energia', '100')
    set_impostazione('stress', '15')

def get_prodotti_disponibili_df():
    with get_connection() as conn:
        try:
            return pd.read_sql_query("""
                SELECT DISTINCT p.id, p.nome, p.valore_mercato_unitario
                FROM prodotti p
                JOIN lotti l ON p.id = l.prodotto_id
                WHERE l.quantita_attuale > 0
                ORDER BY p.nome ASC
            """, conn)
        except:
            return pd.DataFrame()

def get_lotti_attivi_df():
    with get_connection() as conn:
        try:
            return pd.read_sql_query("""
                SELECT l.id, p.nome AS prodotto, l.codice_lotto, l.quantita_iniziale, l.quantita_attuale, 
                       l.costo_acquisto_unitario, l.data_carico
                FROM lotti l
                JOIN prodotti p ON l.prodotto_id = p.id
                WHERE l.quantita_attuale > 0
                ORDER BY l.data_carico ASC, l.id ASC
            """, conn)
        except:
            return pd.DataFrame()

def get_movimenti_dettagliati_df():
    with get_connection() as conn:
        try:
            return pd.read_sql_query("""
                SELECT m.id, m.data, p.nome AS prodotto, COALESCE(l.codice_lotto, 'N/D') AS codice_lotto,
                       m.tipo, m.quantita, m.prezzo_unitario, m.ricavo_totale, m.costo_totale, 
                       m.margine, COALESCE(m.cliente, 'Anonimo') AS cliente, COALESCE(m.pagamento, 'Subito') AS pagamento
                FROM movimenti m
                JOIN prodotti p ON m.prodotto_id = p.id
                LEFT JOIN lotti l ON m.lotto_id = l.id
                ORDER BY m.data DESC
            """, conn)
        except:
            return pd.DataFrame()

def esegui_simulazione_bot():
    reset_database_totale()
    p_name = get_impostazione('nome_protagonista', 'Hassan')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        prodotti_info = [
            ("Hash Base", 10.0, 15.0),
            ("Amnesia Haze", 15.0, 22.0),
            ("Super Skunk", 12.0, 18.0)
        ]
        for p_nome, scorta_m, val_m in prodotti_info:
            cursor.execute("INSERT OR IGNORE INTO prodotti (nome, unita_misura, valore_mercato_unitario, scorta_minima_g) VALUES (?, 'g', ?, ?)", (p_nome, val_m, scorta_m))
        
        clienti_fittizi = ["Mario Rossi", "Luca Bianchi", "Giulia Verdi", "Sara Neri", "Marco Gialli"]
        for c in clienti_fittizi:
            cursor.execute("INSERT OR IGNORE INTO clienti (nome, fiducia) VALUES (?, 60)", (c,))

        data_inizio = date.today() - timedelta(days=365)
        cursor.execute("SELECT id FROM prodotti WHERE nome = 'Hash Base'")
        p_id_init = cursor.fetchone()[0]
        qta_init = 100.0
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
        """, (p_id_init, l_id_init, qta_init, costo_u_init, costo_tot_init, f"Lotto Iniziale", ts_c))

    for giorno_idx in range(30):
        data_corrente = (date.today() - timedelta(days=30)) + timedelta(days=giorno_idx)
        ts_giorno = datetime.combine(data_corrente, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario, codice_lotto, prodotto_id FROM lotti WHERE quantita_attuale > 0 LIMIT 1")
            lotto_attivo = cursor.fetchone()
            if lotto_attivo:
                l_id, qta_disp, costo_u, cod_lotto, p_id = lotto_attivo
                qta_vendita = min(qta_disp, random.uniform(5.0, 15.0))
                prezzo_unitario = 15.0
                ricavo_totale = qta_vendita * prezzo_unitario
                costo_totale = qta_vendita * costo_u
                margine = ricavo_totale - costo_totale
                nuova_qta = qta_disp - qta_vendita
                data_comp = data_corrente if nuova_qta == 0 else None

                cursor.execute("UPDATE lotti SET quantita_attuale = ?, data_completamento = ? WHERE id = ?", (nuova_qta, data_comp, l_id))
                cursor.execute("""
                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note, data)
                    VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, 'Bot Cliente', 'Subito', ?, ?)
                """, (p_id, l_id, qta_vendita, prezzo_unitario, ricavo_totale, costo_totale, margine, f"Vendita Automatica {cod_lotto}", ts_giorno))
                aggiungi_log_db(cursor, f"🤖 Bot Telegram [{data_corrente.strftime('%d %b')}]: Venduti {qta_vendita:.1f}g per € {ricavo_totale:,.2f}!")

    set_impostazione('simulazione_eseguita', '1')
    set_impostazione('log_strategico_finale', f"Simulazione Bot completata con successo per {p_name}! Tutti i flussi e i lotti sono sincronizzati.")

# HUD
p_name = get_impostazione('nome_protagonista', 'Hassan')
energia_gioco = get_impostazione('energia', '100')
stress_gioco = get_impostazione('stress', '15')

with get_connection() as conn:
    try:
        inc_tot = pd.read_sql_query("SELECT SUM(ricavo_totale) FROM movimenti WHERE tipo = 'VENDITA'", conn).iloc[0, 0] or 0.0
        cost_tot = pd.read_sql_query("SELECT SUM(costo_totale) FROM movimenti WHERE tipo = 'CARICO'", conn).iloc[0, 0] or 0.0
        xme_tot = pd.read_sql_query("SELECT SUM(costo_totale) FROM movimenti WHERE tipo = 'XME'", conn).iloc[0, 0] or 0.0
    except:
        inc_tot, cost_tot, xme_tot = 0.0, 0.0, 0.0

cassa_hud = 500.0 + inc_tot - cost_tot - xme_tot

st.markdown(f"""
<div class="game-hud">
    <div class="hud-item">
        <span class="hud-label">👤 Giocatore</span>
        <span class="hud-value" style="color: #f8fafc;">{p_name}</span>
    </div>
    <div class="hud-item">
        <span class="hud-label">💰 Cassa Netta</span>
        <span class="hud-value" style="color: #2ed573;">€ {cassa_hud:,.2f}</span>
    </div>
    <div class="hud-item">
        <span class="hud-label">⚡ Energia</span>
        <span class="hud-value">{energia_gioco}%</span>
    </div>
    <div class="hud-item">
        <span class="hud-label">🤯 Stress</span>
        <span class="hud-value" style="color: {'#ef4444' if int(stress_gioco)>50 else '#38bdf8'};">{stress_gioco}%</span>
    </div>
</div>
""", unsafe_allow_html=True)

placeholder_notifica = st.empty()
tutti_log = get_tutti_log_db()
if tutti_log:
    placeholder_notifica.markdown(f'<div class="alert-banner">📡 <b>Ultimo Evento Bot:</b> {tutti_log[-1]}</div>', unsafe_allow_html=True)
else:
    placeholder_notifica.markdown(f'<div class="alert-banner">📡 <b>Stato:</b> Bot pronto. Avvia la simulazione nel tab apposito per iniziare i flussi automatici.</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💸 Cassa & Vendite", 
    "🚀 Upgrade & Shop", 
    "🚚 Magazzino & Lotti",
    "📊 Statistiche",
    "🎮 Skill & Vita",
    "🤖 Bot & Simulatore"
])

with tab1:
    st.subheader("💸 Gestione Incassi & Scarico")
    tipo_operazione = st.radio("Seleziona Azione", ["Vendita Cliente", "Uscita Personale (XME)"], horizontal=True)
    prodotti_disp_df = get_prodotti_disponibili_df()
    
    if prodotti_disp_df.empty:
        st.warning("⚠️ Magazzino vuoto. Vai nel tab 'Bot & Simulatore' e avvia la simulazione per caricare i primi lotti.")
    else:
        if tipo_operazione == "Vendita Cliente":
            prod_nome = st.selectbox("Prodotto", prodotti_disp_df['nome'].tolist())
            prod_row = prodotti_disp_df[prodotti_disp_df['nome'] == prod_nome].iloc[0]
            p_id = int(prod_row['id'])
            
            with get_connection() as conn:
                lotti_disp = pd.read_sql_query("SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", conn, params=(p_id,))
            qta_tot = lotti_disp['quantita_attuale'].sum() if not lotti_disp.empty else 0
            
            st.info(f"Disponibilità in magazzino: **{qta_tot:,.1f} g**")
            
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                qta_v = st.number_input("Quantità (g)", min_value=0.0, value=0.0, step=0.5)
                tot_euro = st.number_input("Incasso (€)", min_value=0.0, value=0.0, step=1.0)
            with col_v2:
                cliente_nome = st.text_input("Nome Cliente", value="Anonimo")
                pagamento_modo = st.radio("Pagamento", ["Subito", "Dopo (Credito)"], horizontal=True)

            if st.button("Registra Vendita", use_container_width=True):
                if qta_v <= 0 or tot_euro <= 0:
                    st.error("Inserisci quantità e importo validi.")
                elif qta_v > qta_tot:
                    st.error("Quantità superiore alla disponibilità.")
                else:
                    prezzo_u = tot_euro / qta_v
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        rimanente = qta_v
                        for _, lotto in lotti_disp.iterrows():
                            if rimanente <= 0: break
                            l_id = int(lotto['id'])
                            qta_l = float(lotto['quantita_attuale'])
                            prelievo = min(qta_l, rimanente)
                            nuova_qta = qta_l - prelievo
                            rimanente -= prelievo
                            
                            costo_q = prelievo * float(lotto['costo_acquisto_unitario'])
                            ricavo_q = prelievo * prezzo_u
                            margine_q = ricavo_q - costo_q
                            
                            dt_comp = date.today() if nuova_qta == 0 else None
                            cursor.execute("UPDATE lotti SET quantita_attuale = ?, data_completamento = ? WHERE id = ?", (nuova_qta, dt_comp, l_id))
                            cursor.execute("""
                                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note, data)
                                VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (p_id, l_id, prelievo, prezzo_u, ricavo_q, costo_q, margine_q, cliente_nome.capitalize(), pagamento_modo, f"Lotto {lotto['codice_lotto']}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        
                        aggiungi_log_db(cursor, f"Vendita manuale completata: {qta_v}g a {cliente_nome} per € {tot_euro:,.2f}")
                    st.success("✅ Vendita registrata con successo!")
                    st.rerun()

        else:
            lotti_attivi = get_lotti_attivi_df()
            if lotti_attivi.empty:
                st.warning("Nessun lotto attivo per prelievi personali.")
            else:
                with st.form("form_xme_clean"):
                    opzioni = {f"{r['prodotto']} (Lotto: {r['codice_lotto']} - Disp: {r['quantita_attuale']}g)": r['id'] for _, r in lotti_attivi.iterrows()}
                    scelta_lotto_lbl = st.selectbox("Seleziona Lotto", list(opzioni.keys()))
                    l_id_scelto = opzioni[scelta_lotto_lbl]
                    row_l = lotti_attivi[lotti_attivi['id'] == l_id_scelto].iloc[0]
                    
                    qta_x = st.number_input("Quantità (g)", min_value=0.5, max_value=float(row_l['quantita_attuale']), value=5.0)
                    nota_x = st.text_input("Motivo (es. Uso personale, test)")
                    
                    if st.form_submit_button("Conferma Uscita"):
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            nuova_q = float(row_l['quantita_attuale']) - qta_x
                            costo_p = qta_x * float(row_l['costo_acquisto_unitario'])
                            p_id_x = int(get_prodotti_disponibili_df()[get_prodotti_disponibili_df()['nome'] == row_l['prodotto']].iloc[0]['id'])
                            dt_c = date.today() if nueva_q == 0 else None
                            
                            cursor.execute("UPDATE lotti SET quantita_attuale = ?, data_completamento = ? WHERE id = ?", (nuova_q, dt_c, l_id_scelto))
                            cursor.execute("""
                                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, margine, cliente, pagamento, note, data)
                                VALUES (?, ?, 'XME', ?, 0, ?, ?, 'XME', 'Subito', ?, ?)
                            """, (p_id_x, l_id_scelto, qta_x, costo_p, -costo_p, f"XME: {nota_x}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        st.success("Uscita personale registrata.")
                        st.rerun()

with tab2:
    st.subheader("🚀 Shop Upgrade & Automazione Infinita")
    st.markdown("Acquista miglioramenti permanenti per scalare il business più velocemente e aumentare i profitti!")
    
    with get_connection() as conn:
        upgrades_df = pd.read_sql_query("SELECT * FROM upgrades", conn)
        
    for _, up in upgrades_df.iterrows():
        up_id, up_nome, up_lvl, up_costo_base, up_molt, up_desc = up['id'], up['nome'], up['livello'], up['costo_base'], up['moltiplicatore_costo'], up['descrizione']
        costo_attuale = up_costo_base * (up_molt ** up_lvl)
        
        col_u1, col_u2, col_u3 = st.columns([2, 2, 1])
        col_u1.markdown(f"**{up_nome}** (Lv. {up_lvl})<br><small>{up_desc}</small>", unsafe_allow_html=True)
        col_u2.metric("Costo Upgrade", f"€ {costo_attuale:,.2f}")
        
        if col_u3.button("Potenzia", key=f"buy_up_{up_id}", use_container_width=True):
            if cassa_hud >= costo_attuale:
                with get_connection() as conn:
                    conn.execute("UPDATE upgrades SET livello = livello + 1 WHERE id = ?", (up_id,))
                st.success(f"Upgrade '{up_nome}' acquistato con successo!")
                st.rerun()
            else:
                st.error("Fondi insufficienti in cassa!")

with tab3:
    st.subheader("🚚 Stato Magazzino & Lotti Attivi")
    lotti_attivi_df = get_lotti_attivi_df()
    if lotti_attivi_df.empty:
        st.info("Nessun lotto attivo in magazzino.")
    else:
        st.dataframe(lotti_attivi_df[['prodotto', 'codice_lotto', 'quantita_attuale', 'costo_acquisto_unitario', 'data_carico']], use_container_width=True, hide_index=True)

with tab4:
    st.subheader("📊 Statistiche & Andamento Finanziario")
    mov_df = get_movimenti_dettagliati_df()
    
    if mov_df.empty:
        st.info("Nessuna statistica disponibile.")
    else:
        incasso_tot = mov_df[mov_df['tipo'] == 'VENDITA']['ricavo_totale'].sum()
        margine_tot = mov_df[mov_df['tipo'] == 'VENDITA']['margine'].sum()
        
        col_s1, col_s2 = st.columns(2)
        col_s1.metric("Incasso Totale", f"€ {incasso_tot:,.2f}")
        col_s2.metric("Margine Netto", f"€ {margine_tot:,.2f}")
        
        st.markdown("---")
        df_chart = mov_df.copy()
        df_chart['Data'] = pd.to_datetime(df_chart['data'])
        df_chart = df_chart.sort_values('Data')
        df_chart['Margine Cumulato'] = df_chart['margine'].cumsum()
        
        chart = alt.Chart(df_chart).mark_line(point=True, strokeWidth=3, color='#38bdf8').encode(
            x=alt.X('Data:T', title='Data'),
            y=alt.Y('Margine Cumulato:Q', title='Margine Netto (€)'),
            tooltip=['Data:T', 'prodotto:N', 'Margine Cumulato:Q']
        ).properties(height=350).configure_view(strokeWidth=0).interactive()
        st.altair_chart(chart, use_container_width=True)

with tab5:
    st.subheader("🎮 Skill Tree & Attività Giornaliere")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if st.button("🎵 Studio Digitakt (Riduci Stress)", use_container_width=True):
            s_corr = max(0, int(stress_gioco) - 10)
            set_impostazione('stress', str(s_corr))
            st.success("Stress ridotto.")
            st.rerun()
    with col_a2:
        if st.button("🪢 Allenamento Heavy Rope (Ricarica Energia)", use_container_width=True):
            e_corr = min(100, int(energia_gioco) + 15)
            set_impostazione('energia', str(e_corr))
            st.success("Energia ricaricata.")
            st.rerun()

with tab6:
    st.subheader("🤖 Bot Telegram & Simulatore Anno")
    p_name_input = st.text_input("Nome Protagonista", value=p_name)
    if p_name_input != p_name and p_name_input.strip():
        set_impostazione('nome_protagonista', p_name_input.strip().capitalize())
        st.rerun()
        
    c_b1, c_b2 = st.columns(2)
    with c_b1:
        if st.button("🚀 Avvia Bot & Simulazione", use_container_width=True):
            with st.spinner("Il bot sta avviando la simulazione e i flussi automatici..."):
                esegui_simulazione_bot()
                time.sleep(1)
            st.success("Simulazione del bot avviata e lotti caricati con successo!")
            st.rerun()
    with c_b2:
        if st.button("🗑️ Reset Totale Partita", use_container_width=True):
            reset_database_totale()
            st.success("Partita resettata.")
            st.rerun()

    log_finale = get_impostazione('log_strategico_finale', '')
    if log_finale:
        st.text_area("Report Bot & Storico", value=log_finale, height=200)