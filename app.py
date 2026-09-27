import sqlite3
import random
from datetime import datetime, date
import pandas as pd
import streamlit as st

# ==========================================
# 1. CONFIGURAZIONE PAGINA E CSS CUSTOM
# ==========================================
st.set_page_config(
    page_title="LaBzz - Empire Tycoon Manager",
    page_icon="📦",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Titan+One&display=swap');

    .stApp {
        background-color: #090c17 !important;
        background: linear-gradient(180deg, #070a14 0%, #090c17 50%, #0d1222 100%) !important;
        color: #f8fafc !important;
        font-family: 'Fredoka', sans-serif !important;
    }

    h1, h2, h3 {
        font-family: 'Titan One', cursive !important;
        color: #ffffff !important;
        text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.6) !important;
    }

    .stat-card {
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 14px !important;
        padding: 15px !important;
        text-align: center !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4) !important;
    }

    .stButton>button {
        font-family: 'Fredoka', sans-serif !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        height: 3em !important;
        background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. PERSISTENZA DATABASE SQLITE
# ==========================================
DB_NAME = "game_magazzino_streamlit.db"

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
            valore_mercato REAL DEFAULT 5.0,
            scorta_minima REAL DEFAULT 50.0
        )""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prodotto_id INTEGER NOT NULL,
            codice_lotto TEXT NOT NULL,
            quantita_iniziale REAL NOT NULL,
            quantita_attuale REAL NOT NULL,
            costo_acquisto_unitario REAL NOT NULL,
            data_carico DATE NOT NULL,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id) ON DELETE CASCADE
        )""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prodotto_id INTEGER,
            lotto_id INTEGER,
            tipo TEXT,
            quantita REAL,
            prezzo_unitario REAL,
            ricavo_totale REAL,
            costo_totale REAL,
            margine REAL,
            cliente TEXT,
            pagamento TEXT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        cursor.execute("SELECT COUNT(*) FROM prodotti")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO prodotti (nome, valore_mercato, scorta_minima) VALUES ('Varietà Premium', 4.5, 50.0)")
            p_id = cursor.lastrowid
            cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico) VALUES (?, 'LOTTO-001', 500.0, 500.0, 1.2, ?)", (p_id, date.today()))

init_db()

# ==========================================
# 3. STATO DEL GIOCATORE (SESSION STATE)
# ==========================================
if 'cassa' not in st.session_state:
    st.session_state.cassa = 750.00
if 'energia' not in st.session_state:
    st.session_state.energia = 100
if 'giorno' not in st.session_state:
    st.session_state.giorno = 1
if 'reputazione' not in st.session_state:
    st.session_state.reputazione = 50
if 'log_gioco' not in st.session_state:
    st.session_state.log_gioco = ["🎮 Benvenuto in LaBzz Tycoon! Imposta la tua strategia e scala il mercato."]
if 'evento_attivo' not in st.session_state:
    st.session_state.evento_attivo = "☀️ Mercato Stabile: Condizioni normali di vendita."

def aggiungi_log(testo):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.log_gioco.insert(0, f"[{timestamp}] {testo}")

def verifica_evento_casuale():
    roll = random.random()
    if roll < 0.15:
        spesa = round(random.uniform(30, 80), 2)
        st.session_state.cassa = max(0.0, st.session_state.cassa - spesa)
        st.session_state.evento_attivo = f"⚠️ Ispezione Fiscale: Multa registrata (-€{spesa:.2f})"
        aggiungi_log(st.session_state.evento_attivo)
    elif roll < 0.30:
        st.session_state.reputazione = min(100, st.session_state.reputazione + 10)
        st.session_state.evento_attivo = "📈 Trend Virale sui Social! Reputazione in aumento (+10)"
        aggiungi_log(st.session_state.evento_attivo)
    else:
        st.session_state.evento_attivo = "☀️ Mercato Stabile: Condizioni normali di vendita."

# ==========================================
# 4. AZIONI DI GAMEPLAY
# ==========================================
def az_apri_turno_vendite():
    if st.session_state.energia < 20:
        st.error("❌ Energia troppo bassa! Riposa o attiva il Perk XME.")
        return

    st.session_state.energia -= 20
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.nome, p.valore_mercato, SUM(l.quantita_attuale)
            FROM prodotti p JOIN lotti l ON p.id = l.prodotto_id
            WHERE l.quantita_attuale > 0 GROUP BY p.id
        """)
        prodotti = cursor.fetchall()

        if not prodotti:
            aggiungi_log("⚠️ Magazzino Vuoto! Impossibile vendere. Ordina un nuovo lotto!")
            st.warning("Magazzino vuoto!")
            return

        clienti = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "ClienteVIP"]
        num_clienti = random.randint(2, 6)
        vendite, incasso_totale = 0, 0.0

        for _ in range(num_clienti):
            prod_id, prod_nome, prezzo_u, scorta = random.choice(prodotti)
            cliente = random.choice(clienti)
            
            if prezzo_u <= (prezzo_u * random.uniform(0.85, 1.35)) and scorta > 0:
                qta = min(scorta, float(random.choice([10, 20, 50])))
                
                cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", (prod_id,))
                lotti = cursor.fetchall()
                qta_restante = qta
                costo_op = 0.0

                for l_id, l_qta, l_costo in lotti:
                    if qta_restante <= 0:
                        break
                    prelievo = min(l_qta, qta_restante)
                    cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale - ? WHERE id = ?", (prelievo, l_id))
                    qta_restante -= prelievo
                    costo_op += prelievo * l_costo

                ricavo = qta * prezzo_u
                margine = ricavo - costo_op
                pagamento = "Dopo (Credito)" if (random.random() < 0.2 and cliente != "ClienteVIP") else "Subito"

                if pagamento == "Subito":
                    st.session_state.cassa += ricavo
                    incasso_totale += ricavo

                cursor.execute("""
                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento)
                    VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?)
                """, (prod_id, lotti[0][0], qta, prezzo_u, ricavo, costo_op, margine, cliente, pagamento))

                vendite += 1
                aggiungi_log(f"✅ Venduti {qta}g a {cliente} per €{ricavo:.2f} ({pagamento})")

        if vendite > 0:
            st.session_state.reputazione = min(100, st.session_state.reputazione + 2)

def az_riposa():
    st.session_state.giorno += 1
    st.session_state.energia = 100
    spese_fisse = 25.0
    st.session_state.cassa = max(0.0, st.session_state.cassa - spese_fisse)
    aggiungi_log(f"🌙 Giorno {st.session_state.giorno} iniziato. Pagate spese fisse (€{spese_fisse:.2f}).")
    verifica_evento_casuale()

def az_xme_perk():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario FROM lotti WHERE quantita_attuale >= 15 LIMIT 1")
        lotto = cursor.fetchone()
        if lotto:
            l_id, qta_att, costo_u = lotto
            cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale - 15 WHERE id = ?", (l_id,))
            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, margine, cliente, note) VALUES (1, ?, 'XME', 15, ?, ?, 'XME', 'Uso Personale Perk')", (l_id, 15 * costo_u, -(15 * costo_u)))
            st.session_state.energia = min(100, st.session_state.energia + 35)
            aggiungi_log("🧪 Scaricati 15g per Uso Personale (XME). Energia +35%!")
        else:
            st.error("Servono almeno 15g in un lotto per fare XME!")

def az_compra_lotto():
    costo_lotto = 200.0
    qta_lotto = 200.0
    if st.session_state.cassa >= costo_lotto:
        st.session_state.cassa -= costo_lotto
        with get_connection() as conn:
            cursor = conn.cursor()
            cod = f"L-G{st.session_state.giorno}-{random.randint(10,99)}"
            cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico) VALUES (1, ?, ?, ?, 1.0, ?)", (cod, qta_lotto, qta_lotto, date.today()))
            l_id = cursor.lastrowid
            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente) VALUES (1, ?, 'CARICO', ?, ?, 'Fornitore')", (l_id, qta_lotto, costo_lotto))
        aggiungi_log(f"📦 Acquistato nuovo lotto {cod} (200g) per €{costo_lotto:.2f}")
    else:
        st.error("Cassa insufficiente per acquistare un nuovo lotto!")

# ==========================================
# 5. DASHBOARD UI STREAMLIT
# ==========================================
st.title("📦 LaBzz - Empire Tycoon Manager")

# HEADER STATISTICHE
c1, c2, c3, c4 = st.columns(4)
c1.metric("💵 Cassa Liquida", f"€ {st.session_state.cassa:,.2f}")
c2.metric("⚡ Energia Imprenditore", f"{st.session_state.energia}%")
c3.metric("⭐ Reputazione", f"{st.session_state.reputazione}/100")
c4.metric("📅 Giorno", f"Giorno {st.session_state.giorno}")

st.info(f"**Stato Mercato:** {st.session_state.evento_attivo}")

st.markdown("---")

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("⚡ Pannello Controllo Operativo")
    b1, b2, b3, b4 = st.columns(4)
    
    with b1:
        if st.button("🏪 Apri Turno Vendite"):
            az_apri_turno_vendite()
            st.rerun()
    with b2:
        if st.button("💤 Riposa e Passa Giorno"):
            az_riposa()
            st.rerun()
    with b3:
        if st.button("🧪 Consumo XME (+35% E)"):
            az_xme_perk()
            st.rerun()
    with b4:
        if st.button("🛒 Ordina Lotto (€200)"):
            az_compra_lotto()
            st.rerun()

    st.markdown("---")
    
    tab_lotti, tab_mov = st.tabs(["📦 Lotti in Magazzino", "📜 Registro Movimenti DB"])
    
    with tab_lotti:
        with get_connection() as conn:
            df_lotti = pd.read_sql_query("SELECT l.codice_lotto, p.nome, l.quantita_attuale, l.costo_acquisto_unitario FROM lotti l JOIN prodotti p ON l.prodotto_id = p.id WHERE l.quantita_attuale > 0", conn)
        st.dataframe(df_lotti, use_container_width=True, hide_index=True)

    with tab_mov:
        with get_connection() as conn:
            df_mov = pd.read_sql_query("SELECT tipo, quantita, ricavo_totale, costo_totale, margine, cliente, pagamento, data FROM movimenti ORDER BY id DESC LIMIT 15", conn)
        st.dataframe(df_mov, use_container_width=True, hide_index=True)

with col_right:
    st.subheader("📟 Console Eventi Live")
    for log in st.session_state.log_gioco[:10]:
        st.caption(log)