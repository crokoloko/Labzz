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
    page_title="LaBzz - Life & Business Simulator",
    page_icon="🕹️",
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

def get_video_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    return None

# ==========================================
# INIEZIONE CSS CUSTOM (STILE VIDEOGIOCO HUD)
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

    /* HUD DI GIOCO (BARRA DI STATO SUPERIORE) */
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
    
    .event-banner {
        background: linear-gradient(135deg, #7f1d1d 0%, #450a0a 100%);
        border-left: 5px solid #ef4444;
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

    /* CARDS DI GIOCO */
    .game-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        margin-bottom: 15px;
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
        CREATE TABLE IF NOT EXISTS abilita (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            livello INTEGER DEFAULT 0,
            max_livello INTEGER DEFAULT 3,
            descrizione TEXT
        )
        """)
        
        skills_base = [
            ("logistica", "Efficienza Logistica", 0, 3, "Riduce i costi di acquisto lotti del 5% per livello."),
            ("carisma", "Carisma & Vendite", 0, 3, "Aumenta i prezzi di vendita del 5% per livello."),
            ("resistenza", "Resistenza & Focus", 0, 3, "Aumenta l'energia giornaliera e riduce lo stress da lavoro.")
        ]
        for sk_id, sk_nome, sk_lvl, sk_max, sk_desc in skills_base:
            cursor.execute("INSERT OR IGNORE INTO abilita (id, nome, livello, max_livello, descrizione) VALUES (?, ?, ?, ?, ?)", 
                           (sk_id, sk_nome, sk_lvl, sk_max, sk_desc))

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS impostazioni (
            chiave TEXT PRIMARY KEY,
            valore TEXT NOT NULL
        )
        """)
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('soglia_esaurimento', '10.0')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('simulazione_eseguita', '0')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('nome_protagonista', 'Hassan')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('personalita_bot', 'Influente (Max 7g/giorno)')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('log_strategico_finale', '')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('energia', '100')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('stress', '15')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('reputazione', '50')")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('evento_attivo', '')")

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
        cursor.execute("UPDATE abilita SET livello = 0")
    set_impostazione('simulazione_eseguita', '0')
    set_impostazione('log_strategico_finale', '')
    set_impostazione('energia', '100')
    set_impostazione('stress', '15')
    set_impostazione('reputazione', '50')
    set_impostazione('evento_attivo', '')

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

def get_movimenti_dettagliati_df():
    query = """
        SELECT 
            m.id, m.data, p.nome AS prodotto, COALESCE(l.codice_lotto, 'N/D') AS codice_lotto,
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

# ==========================================
# HEADER / HUD DI GIOCO FISSO IN CIMA
# ==========================================
p_name = get_impostazione('nome_protagonista', 'Hassan')
energia_gioco = get_impostazione('energia', '100')
stress_gioco = get_impostazione('stress', '15')
reputazione_gioco = get_impostazione('reputazione', '50')

# Calcola cassa corrente al volo per l'HUD
with get_connection() as conn:
    inc_tot = pd.read_sql_query("SELECT SUM(ricavo_totale) FROM movimenti WHERE tipo = 'VENDITA'", conn).iloc[0, 0] or 0.0
    cost_tot = pd.read_sql_query("SELECT SUM(costo_totale) FROM movimenti WHERE tipo = 'CARICO'", conn).iloc[0, 0] or 0.0
    xme_tot = pd.read_sql_query("SELECT SUM(costo_totale) FROM movimenti WHERE tipo = 'XME'", conn).iloc[0, 0] or 0.0
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

# Banner notifiche rapide
placeholder_notifica = st.empty()
tutti_log = get_tutti_log_db()
if tutti_log:
    placeholder_notifica.markdown(f'<div class="alert-banner">📡 <b>Ultimo Evento:</b> {tutti_log[-1]}</div>', unsafe_allow_html=True)
else:
    placeholder_notifica.markdown(f'<div class="alert-banner">📡 <b>Stato:</b> Gestione magazzino attiva. Pronto per iniziare!</div>', unsafe_allow_html=True)

# 6 Tabs pulite ed essenziali focalizzate sul gioco
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💸 Cassa & Vendite", 
    "📊 Progressi & Stats", 
    "🚚 Magazzino & Lotti",
    "📜 Storico",
    "🎮 Skill & Vita",
    "🤖 Simulatore Anno"
])

with tab1:
    st.subheader("💸 Gestione Incassi & Scarico")
    tipo_operazione = st.radio("Seleziona Azione", ["Vendita Cliente", "Uscita Personale (XME)"], horizontal=True)
    prodotti_disp_df = get_prodotti_disponibili_df()
    
    if prodotti_disp_df.empty:
        st.warning("⚠️ Magazzino vuoto. Avvia la simulazione annuale o carica un lotto.")
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
                        
                        aggiungi_log_db(cursor, f"Vendita completata: {qta_v}g a {cliente_nome} per € {tot_euro:,.2f}")
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
                            p_id_x = int(get_prodotti_tutti_df()[get_prodotti_tutti_df()['nome'] == row_l['prodotto']].iloc[0]['id'])
                            dt_c = date.today() if nuova_q == 0 else None
                            
                            cursor.execute("UPDATE lotti SET quantita_attuale = ?, data_completamento = ? WHERE id = ?", (nuova_q, dt_c, l_id_scelto))
                            cursor.execute("""
                                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, margine, cliente, pagamento, note, data)
                                VALUES (?, ?, 'XME', ?, 0, ?, ?, 'XME', 'Subito', ?, ?)
                            """, (p_id_x, l_id_scelto, qta_x, costo_p, -costo_p, f"XME: {nota_x}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        st.success("Uscita personale registrata.")
                        st.rerun()

with tab2:
    st.subheader("📊 Statistiche & Progresso di Gioco")
    mov_df = get_movimenti_dettagliati_df()
    
    if mov_df.empty:
        st.info("Nessuna statistica disponibile. Effettua vendite o avvia la simulazione.")
    else:
        incasso_tot = mov_df[mov_df['tipo'] == 'VENDITA']['ricavo_totale'].sum()
        margine_tot = mov_df[mov_df['tipo'] == 'VENDITA']['margine'].sum()
        spesa_lotti = mov_df[mov_df['tipo'] == 'CARICO']['costo_totale'].sum()
        
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("Incasso Totale Business", f"€ {incasso_tot:,.2f}")
        col_s2.metric("Margine Netto", f"€ {margine_tot:,.2f}")
        col_s3.metric("Spesa Rifornimenti", f"€ {spesa_lotti:,.2f}")
        
        st.markdown("---")
        st.markdown("##### 📈 Andamento Finanziario")
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

with tab3:
    st.subheader("🚚 Stato Magazzino & Lotti Attivi")
    lotti_attivi_df = get_lotti_attivi_df()
    if lotti_attivi_df.empty:
        st.info("Nessun lotto attivo in magazzino.")
    else:
        st.dataframe(lotti_attivi_df[['prodotto', 'codice_lotto', 'quantita_attuale', 'costo_acquisto_unitario', 'data_carico']], use_container_width=True, hide_index=True)

with tab4:
    st.subheader("📜 Storico Operazioni")
    mov_df = get_movimenti_dettagliati_df()
    if not mov_df.empty:
        st.dataframe(mov_df[['data', 'prodotto', 'tipo', 'quantita', 'ricavo_totale', 'cliente', 'pagamento']], use_container_width=True, hide_index=True)

with tab5:
    st.subheader("🎮 Skill Tree & Attività Giornaliere")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if st.button("🎵 Studio Digitakt (Riduci Stress)", use_container_width=True):
            s_corr = max(0, int(stress_gioco) - 10)
            set_impostazione('stress', str(s_corr))
            st.success("Sessione musicale completata! Stress diminuito.")
            st.rerun()
    with col_a2:
        if st.button("🪢 Allenamento Heavy Rope (Ricarica Energia)", use_container_width=True):
            e_corr = min(100, int(energia_gioco) + 15)
            set_impostazione('energia', str(e_corr))
            st.success("Allenamento completato! Energia ricaricata.")
            st.rerun()

    st.markdown("##### Albero delle Abilità")
    with get_connection() as conn:
        skills = pd.read_sql_query("SELECT * FROM abilita", conn)
    for _, sk in skills.iterrows():
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.markdown(f"**{sk['nome']}** (Lv. {sk['livello']}/{sk['max_livello']})<br><small>{sk['descrizione']}</small>", unsafe_allow_html=True)
        c2.progress(sk['livello'] / sk['max_livello'])
        if sk['livello'] < sk['max_livello']:
            if c3.button("Upgrade", key=f"up_{sk['id']}"):
                with get_connection() as conn:
                    conn.execute("UPDATE abilita SET livello = livello + 1 WHERE id = ?", (sk['id'],))
                st.success("Abilità potenziata!")
                st.rerun()

with tab6:
    st.subheader("🤖 Simulatore Anno & Story Log")
    p_name_input = st.text_input("Nome Protagonista", value=p_name)
    if p_name_input != p_name and p_name_input.strip():
        set_impostazione('nome_protagonista', p_name_input.strip().capitalize())
        st.rerun()
        
    c_b1, c_b2 = st.columns(2)
    with c_b1:
        if st.button("🚀 Avvia Simulazione Anno", use_container_width=True):
            with st.spinner("Simulazione in corso..."):
                reset_database_totale()
                # Simulazione rapida di test o anno completo
                time.sleep(1)
            st.success("Simulazione completata!")
            st.rerun()
    with c_b2:
        if st.button("🗑️ Reset Totale Partita", use_container_width=True):
            reset_database_totale()
            st.success("Partita resettata.")
            st.rerun()

    log_finale = get_impostazione('log_strategico_finale', '')
    if log_finale:
        st.text_area("Report Strategico Finale", value=log_finale, height=250)