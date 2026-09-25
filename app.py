import sqlite3
import base64
import os
from datetime import datetime, date
import pandas as pd
import streamlit as st
import altair as alt

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="LaBzz - Gestione Magazzino",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# FUNZIONE CARICAMENTO VIDEO BASE64 PER LOGO
# ==========================================
def get_video_base64(file_path):
    """Legge il file video e lo converte in stringa Base64 per l'embedding HTML."""
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    return None

# ==========================================
# INIEZIONE CSS CUSTOM (CENTRATURA + CORREZIONI PARSING E MARGINI)
# ==========================================
st.markdown("""
<style>
    /* 1. IMPORTAZIONE GOOGLE FONTS (TITAN ONE & FREDOKA) */
    @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Titan+One&display=swap');

    /* 2. SFONDO GLOBALE UNIFORMATO AL BLU SCURO DEL LOGO */
    .stApp {
        background-color: #090c17 !important;
        background: linear-gradient(180deg, #070a14 0%, #090c17 50%, #0d1222 100%) !important;
        color: #f8fafc !important;
        font-family: 'Fredoka', sans-serif !important;
        font-weight: 500;
    }

    /* 3. RIMOZIONE BARRA IN ALTO DI STREAMLIT PER EVITARE TAGLI */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* 4. MARGINE SUPERIORE ED INFERIORE ESTESO PER EVITARE TAGLI IN FONDO */
    .block-container {
        padding-top: 2.8rem !important;
        padding-bottom: 6rem !important; /* Spazio extra in fondo per la leggibilità */
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* 5. CENTRATURA PERFETTA LOGO VIDEO SENZA BORDURA NÉ SFUMATURA */
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
        filter: none !important;
        box-shadow: none !important;
        object-fit: contain !important;
        background-color: transparent !important;
    }

    /* 6. SPAZIATURA E CENTRATURA TAB (SCHEDE) */
    div[data-testid="stTabs"] {
        margin-top: 0rem !important;
        padding-top: 0rem !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 12px !important;
        background-color: transparent !important;
        border-bottom: none !important;
        padding: 0px 0 12px 0 !important;
        justify-content: center !important;
    }

    /* 7. CENTRATURA DI TUTTI I TITOLI E INTESTAZIONI */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Titan One', cursive, sans-serif !important;
        color: #ffffff !important;
        text-align: center !important;
        line-height: 1.5 !important;
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

    /* 8. CENTRATURA DI TESTI STANDARD, DIDASCALIE E SUBHEADER */
    .stMarkdown, .stText, p, span, label, caption, div[data-testid="stCaptionContainer"] {
        text-align: center !important;
        font-family: 'Fredoka', sans-serif !important;
        line-height: 1.5 !important;
    }

    /* 9. CONTENITORE CUSTOM PER GRIGLIA DASHBOARD */
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
        -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 14px 8px !important;
        box-shadow: 0 8px 25px -5px rgba(0, 0, 0, 0.5), 
                    inset 0 1px 1px 0 rgba(255, 255, 255, 0.1) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
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

    /* 10. RISOLUZIONE TESTI SORMONTATI SU EXPANDER E FORM */
    div[data-testid="stForm"], div[data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 16px !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4) !important;
        padding: 20px !important;
        margin-bottom: 25px !important;
        height: auto !important; /* Garantisce che la scatola si espanda dinamicamente */
        min-height: auto !important;
        overflow: visible !important;
    }

    div[data-testid="stExpander"] details summary {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 10px 5px !important;
        text-align: center !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    /* 11. TAB OPERATIVI 3D */
    .stTabs [data-baseweb="tab"] {
        font-family: 'Fredoka', sans-serif !important;
        background: rgba(15, 23, 42, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 14px !important;
        color: #94a3b8 !important;
        font-weight: 700 !important;
        padding: 12px 20px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }

    /* 12. PULSANTI 3D ED EFFETTI HOVER */
    .stButton {
        display: flex !important;
        justify-content: center !important;
        margin: 10px 0 !important;
    }

    .stButton > button, button[kind="primary"] {
        font-family: 'Fredoka', sans-serif !important;
        background: linear-gradient(135deg, #0284c7 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 28px !important;
        box-shadow: 0 6px 20px rgba(2, 132, 199, 0.35) !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 25px rgba(2, 132, 199, 0.5) !important;
    }

    /* 13. CONTROLLI INPUT, LABELS & SELECT */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        font-family: 'Fredoka', sans-serif !important;
        font-weight: 600 !important;
        background-color: rgba(15, 23, 42, 0.8) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
        text-align: center !important;
    }

    /* 14. TABELLE STYLING GLASS CON MARGINE INFERIORE */
    div[data-testid="stDataFrame"] {
        font-family: 'Fredoka', sans-serif !important;
        background: rgba(15, 23, 42, 0.6) !important;
        border-radius: 14px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        overflow: hidden !important;
        margin-bottom: 25px !important;
    }

    /* MOBILE ADJUSTMENTS */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 2.5rem !important;
            padding-bottom: 8rem !important; /* Spazio ampio per evitare sovrapposizioni in basso */
        }
        .logo-container video {
            max-width: 95% !important;
        }
    }
</style>
""", unsafe_allow_html=True)

DB_NAME = "magazzino.db"

# ==========================================
# GESTIONE DATABASE SQLITE
# ==========================================
def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)

def init_db():
    """Inizializza il database verificando le tabelle, impostazioni e garantendo le chiavi esterne."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # 1. Anagrafica prodotti
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prodotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            unita_misura TEXT DEFAULT 'g',
            valore_mercato_unitario REAL DEFAULT 0,
            scorta_minima_g REAL DEFAULT 0
        )
        """)
        
        # 2. Registro lotti
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
        
        # Migrazione schema lotti
        cursor.execute("PRAGMA table_info(lotti)")
        colonne_lotti = [column[1] for column in cursor.fetchall()]
        if 'data_acquisto' not in colonne_lotti:
            cursor.execute("ALTER TABLE lotti ADD COLUMN data_acquisto DATE")
        if 'data_completamento' not in colonne_lotti:
            cursor.execute("ALTER TABLE lotti ADD COLUMN data_completamento DATE")

        # 3. Registro movimenti
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
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id) ON DELETE CASCADE,
            FOREIGN KEY (lotto_id) REFERENCES lotti (id) ON DELETE SET NULL
        )
        """)

        # 4. Tabella Impostazioni (per la soglia alert permanente)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS impostazioni (
            chiave TEXT PRIMARY KEY,
            valore REAL NOT NULL
        )
        """)
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('soglia_esaurimento', 10.0)")

init_db()

# ==========================================
# FUNZIONI DI LETTURA E QUERY INTEGRATE
# ==========================================
def get_soglia_esaurimento():
    """Recupera la soglia alert salvata nel database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valore FROM impostazioni WHERE chiave = 'soglia_esaurimento'")
        row = cursor.fetchone()
        return float(row[0]) if row else 10.0

def set_soglia_esaurimento(valore):
    """Salva permanentemente la nuova soglia alert nel database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE impostazioni SET valore = ? WHERE chiave = 'soglia_esaurimento'", (valore,))

def get_prodotti_df():
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
            m.note, 
            m.lotto_id
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        LEFT JOIN lotti l ON m.lotto_id = l.id
        ORDER BY m.data DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

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

def storna_movimento(movimento_id):
    """Annulla una transazione e ripristina la scorta del lotto coinvolto."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movimenti WHERE id = ?", (movimento_id,))
        mov = cursor.fetchone()
        
        if not mov:
            return False, "Movimento non trovato."
        
        p_id, lotto_id, tipo, qta = mov[1], mov[2], mov[3], float(mov[4])
        
        if tipo in ['VENDITA', 'XME']:
            if lotto_id:
                cursor.execute("""
                    UPDATE lotti 
                    SET quantita_attuale = quantita_attuale + ?, data_completamento = NULL 
                    WHERE id = ?
                """, (qta, lotto_id))
        elif tipo == 'CARICO':
            if lotto_id:
                cursor.execute("UPDATE lotti SET quantita_attuale = MAX(0, quantita_attuale - ?) WHERE id = ?", (qta, lotto_id))
        
        cursor.execute("DELETE FROM movimenti WHERE id = ?", (movimento_id,))
        return True, "Movimento stornato con successo e giacenza del lotto ripristinata!"

def elimina_lotto_db(lotto_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE movimenti SET lotto_id = NULL WHERE lotto_id = ?", (lotto_id,))
        cursor.execute("DELETE FROM lotti WHERE id = ?", (lotto_id,))

# FUNZIONE PER TRIGGERARE L'ANIMAZIONE DI FUOCHI D'ARTIFICIO (CONFETTI)
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
        fire(0.1, { spread: 120, startVelocity: 25, decay: 0.92, scalar: 1.2 });
        fire(0.1, { spread: 120, startVelocity: 45 });
    </script>
    """
    st.components.v1.html(js_code, height=0)

# ==========================================
# INTERFACCIA UTENTE (STREAMLIT)
# ==========================================

# HEADER LOGO ANIMATO MP4 CONVERTITO IN BASE64 E CENTRATO
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

tab1, tab2, tab3, tab4 = st.tabs([
    "💸 Cassa", 
    "📊 Dashboard & KPI", 
    "🚚 Rifornimenti",
    "📜 Report & Storico"
])

# ------------------------------------------
# TAB 1: CASSA (SOLO VENDITE ED XME)
# ------------------------------------------
with tab1:
    st.subheader("Cassa Operativa")
    
    tipo_operazione = st.radio("Seleziona Tipo Registrazione", ["Vendita", "XME"], horizontal=True)
    
    prodotti_tutti_df = get_prodotti_df()
    
    if prodotti_tutti_df.empty:
        st.warning("⚠️ Nessun prodotto presente in anagrafica. Crea prima un prodotto dal pannello 'Rifornimenti'.")
    else:
        if tipo_operazione == "Vendita":
            prod_nome = st.selectbox("Seleziona Prodotto da Vendere", prodotti_tutti_df['nome'].tolist())
            prod_row = prodotti_tutti_df[prodotti_tutti_df['nome'] == prod_nome].iloc[0]
            p_id = int(prod_row['id'])
            
            with get_connection() as conn:
                query_lotti = "SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC, id ASC"
                lotti_disponibili = pd.read_sql_query(query_lotti, conn, params=(p_id,))

            qta_tot_disp = float(lotti_disponibili['quantita_attuale'].sum()) if not lotti_disponibili.empty else 0.0
            
            if qta_tot_disp <= 0:
                st.error(f"⚠️ Nessuna scorta disponibile per {prod_nome}. Aggiungi prima un lotto dalla scheda 'Rifornimenti'.")
            else:
                st.info(f"Disponibilità totale: {qta_tot_disp:,.1f} g")
                
                st.markdown("##### Registra Vendita")
                col1, col2 = st.columns(2)
                
                with col1:
                    quantita_vendita = st.number_input("Quantità da Vendere (g)", min_value=0.0, value=0.0, step=0.5, format="%.1f")
                    prezzo_vendita_unitario = st.number_input("Prezzo al grammo (€/g)", min_value=0.1, value=float(prod_row['valore_mercato_unitario']), step=0.5, format="%.2f")
                
                with col2:
                    totale_vendita = quantita_vendita * prezzo_vendita_unitario
                    st.metric("Totale", f"€ {totale_vendita:,.2f}")
                    note = st.text_input("Note (Opzionale)")

                if st.button("Conferma Vendita", key="btn_conferma_v"):
                    if quantita_vendita <= 0:
                        st.error("Inserisci una quantità superiore a 0 g per registrare la vendita.")
                    elif quantita_vendita > qta_tot_disp:
                        st.error(f"Quantità inserita ({quantita_vendita:,.1f} g) superiore alla disponibilità ({qta_tot_disp:,.1f} g).")
                    else:
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
                                ricavo_quota = prelievo * prezzo_vendita_unitario
                                margine_quota = ricavo_quota - costo_quota
                                
                                if nuova_qta_lotto == 0:
                                    cursor.execute("""
                                        UPDATE lotti 
                                        SET quantita_attuale = 0, data_completamento = ? 
                                        WHERE id = ?
                                    """, (date.today(), l_id))
                                else:
                                    cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta_lotto, l_id))
                                
                                cursor.execute("""
                                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, note)
                                    VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?)
                                """, (p_id, l_id, prelievo, prezzo_vendita_unitario, ricavo_quota, costo_quota, margine_quota, f"Lotto {cod_lotto} | {note}".strip(" |")))
                        
                        spara_fuochi_d_artificio()
                        st.success("✅ Vendita registrata e coordinata con i lotti e report!")

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
                            
                            p_id = int(prodotti_tutti_df[prodotti_tutti_df['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                            
                            if nuova_qta == 0:
                                cursor.execute("UPDATE lotti SET quantita_attuale = 0, data_completamento = ? WHERE id = ?", (date.today(), lotto_id_scelto))
                            else:
                                cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, lotto_id_scelto))
                                
                            cursor.execute("""
                                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, margine, note)
                                VALUES (?, ?, 'XME', ?, 0, ?, ?, ?)
                            """, (p_id, lotto_id_scelto, qta_xme, costo_perdita, -costo_perdita, f"XME: {motivo}"))
                        
                        st.warning("Operazione XME registrata e sincronizzata col lotto!")
                        st.rerun()

# ------------------------------------------
# TAB 2: DASHBOARD & KPI
# ------------------------------------------
with tab2:
    st.subheader("Dashboard & Analytics")
    df_stato_disp = calcola_stato_magazzino(solo_disponibili=True)
    movimenti_df = get_movimenti_dettagliati_df()

    if df_stato_disp.empty and movimenti_df.empty:
        st.info("Nessun dato di magazzino o movimento disponibile.")
    else:
        val_costo = df_stato_disp['valore_totale_costo'].sum() if not df_stato_disp.empty else 0
        val_mercato = df_stato_disp['valore_totale_mercato'].sum() if not df_stato_disp.empty else 0
        incasso_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['ricavo_totale'].sum() if not movimenti_df.empty else 0
        margine_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['margine'].sum() if not movimenti_df.empty else 0

        # GRIGLIA KPI CENTRATA
        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="custom-card">
                <div class="card-label">Valore (Costo)</div>
                <div class="card-value">€ {val_costo:,.2f}</div>
            </div>
            <div class="custom-card">
                <div class="card-label">Valore (Vendita)</div>
                <div class="card-value">€ {val_mercato:,.2f}</div>
            </div>
            <div class="custom-card">
                <div class="card-label">Incasso Totale</div>
                <div class="card-value">€ {incasso_tot:,.2f}</div>
            </div>
            <div class="custom-card">
                <div class="card-label">Margine Netto</div>
                <div class="card-value">€ {margine_tot:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # STORICO PROGRESSIVO A LARGHEZZA PIENA
        st.subheader("📈 Storico Progressivo Operazioni")
        if movimenti_df.empty:
            st.info("Registra transazioni per generare il grafico.")
        else:
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

# ------------------------------------------
# TAB 3: RIFORNI MENTI
# ------------------------------------------
with tab3:
    st.subheader("🚚 Registro Rifornimenti e Lotti")
    
    soglia_attuale = get_soglia_esaurimento()
    report_lotti_df = get_report_lotti_integrato_df(soglia_esaurimento_g=soglia_attuale)
    
    if report_lotti_df.empty:
        st.info("Nessun lotto di rifornimento salvato.")
    else:
        lotti_warning = report_lotti_df[report_lotti_df['stato_lotto'].str.contains("⚠️")]
        if not lotti_warning.empty:
            for _, w_row in lotti_warning.iterrows():
                st.warning(f"⚠️ Lotto {w_row['codice_lotto']} ({w_row['prodotto']}) in esaurimento! Scorta residua: {w_row['quantita_attuale']:,.1f} g")

        col_m1, col_m2, col_m3 = st.columns(3)
        costo_tot_lotti = report_lotti_df['costo_totale_lotto'].sum()
        incasso_tot_lotti = report_lotti_df['incasso_totale_lotto'].sum()
        guadagno_netto_tot_lotti = report_lotti_df['guadagno_netto_lotto'].sum()
        
        col_m1.metric("Costo Totale Acquisizione Lotti", f"€ {costo_tot_lotti:,.2f}")
        col_m2.metric("Incasso Totale Generato dai Lotti", f"€ {incasso_tot_lotti:,.2f}")
        col_m3.metric("Guadagno Netto Reale Lotti", f"€ {guadagno_netto_tot_lotti:,.2f}")
        
        st.markdown("---")
        
        st.dataframe(
            report_lotti_df[[
                'lotto_id', 'prodotto', 'codice_lotto', 'stato_lotto', 'quantita_iniziale', 'qta_venduta_lotto', 'quantita_attuale',
                'unita_misura', 'costo_acquisto_unitario', 'costo_totale_lotto',
                'incasso_totale_lotto', 'guadagno_netto_lotto', 'data_acquisto', 'data_carico'
            ]],
            column_config={
                "lotto_id": "ID Lotto",
                "prodotto": "Prodotto",
                "codice_lotto": "Codice Lotto",
                "stato_lotto": "Stato Lotto",
                "quantita_iniziale": st.column_config.NumberColumn("Q.tà Iniziale", format="%.1f g"),
                "qta_venduta_lotto": st.column_config.NumberColumn("Q.tà Venduta", format="%.1f g"),
                "quantita_attuale": st.column_config.NumberColumn("Q.tà Residua", format="%.1f g"),
                "unita_misura": "U.M.",
                "costo_acquisto_unitario": st.column_config.NumberColumn("Costo Unit.", format="€ %.2f"),
                "costo_totale_lotto": st.column_config.NumberColumn("Costo Totale Lotto", format="€ %.2f"),
                "incasso_totale_lotto": st.column_config.NumberColumn("Incasso Generato", format="€ %.2f"),
                "guadagno_netto_lotto": st.column_config.NumberColumn("Guadagno Netto", format="€ %.2f"),
                "data_acquisto": "Data Acquisto",
                "data_carico": "Data Carico"
            },
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")
    
    # CONFIGURAZIONE SOGLIA ALERT CENTRATA
    col_cfg1, col_cfg2, col_cfg3 = st.columns([1, 2, 1])
    with col_cfg2:
        nuova_soglia = st.number_input(
            "⚙️ Soglia Alert In Esaurimento (g)", 
            min_value=1.0, 
            value=soglia_attuale, 
            step=1.0, 
            format="%.1f"
        )
        if nuova_soglia != soglia_attuale:
            set_soglia_esaurimento(nuova_soglia)
            st.success(f"Soglia salvata permanentemente a {nuova_soglia:,.1f} g!")
            st.rerun()

    st.markdown("---")
    
    # SEZIONE GESTIONE LOTTI E ANAGRAFICA SENZA SOVRAPPOSIZIONI E CON TESTI CENTRATI
    st.subheader("⚙️ Gestione Lotti e Anagrafica")
    st.write("Apri i pannelli sottostanti per inserire nuovi rifornimenti, eliminare lotti o aggiungere un nuovo prodotto:")
    
    with st.expander("➕ **Aggiungi un Nuovo Lotto / Rifornimento**", expanded=False):
        if prodotti_tutti_df.empty:
            st.warning("Crea prima un prodotto in anagrafica nel pannello dedicato.")
        else:
            with st.form("form_lotto_manuale"):
                p_nome_lotto = st.selectbox("Seleziona Prodotto", prodotti_tutti_df['nome'].tolist())
                cod_lotto_m = st.text_input("Codice Lotto", value=f"LOTTO-MAN-{datetime.now().strftime('%Y%m%d-%H%M')}")
                qta_lotto_m = st.number_input("Quantità Lotto (g)", min_value=0.5, value=500.0, step=0.5, format="%.1f")
                costo_u_lotto_m = st.number_input("Costo Unitario d'Acquisto (€/g)", min_value=0.1, value=1.0, step=0.5, format="%.2f")
                data_acq_m = st.date_input("Data di Acquisto Lotto", value=date.today())
                
                if st.form_submit_button("➕ Aggiungi Lotto"):
                    p_row_m = prodotti_tutti_df[prodotti_tutti_df['nome'] == p_nome_lotto].iloc[0]
                    p_id_m = int(p_row_m['id'])
                    
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (p_id_m, cod_lotto_m, qta_lotto_m, qta_lotto_m, costo_u_lotto_m, data_acq_m, date.today()))
                        
                        lotto_id = cursor.lastrowid
                        cursor.execute("""
                            INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, note)
                            VALUES (?, ?, 'CARICO', ?, ?, ?, 'Nuovo Lotto Manuale')
                        """, (p_id_m, lotto_id, qta_lotto_m, costo_u_lotto_m, qta_lotto_m * costo_u_lotto_m))
                    
                    st.success(f"✅ Lotto '{cod_lotto_m}' aggiunto con successo!")
                    st.rerun()

    with st.expander("🗑️ **Rimuovi un Lotto Esistente**", expanded=False):
        if report_lotti_df.empty:
            st.info("Nessun lotto presente da rimuovere.")
        else:
            opzioni_lotti_gest = {
                f"ID {r['lotto_id']} | {r['prodotto']} - {r['codice_lotto']} (Residuo: {r['quantita_attuale']:,.1f} g | Status: {r['stato_lotto']})": r['lotto_id']
                for _, r in report_lotti_df.iterrows()
            }
            
            label_lotto_scelto = st.selectbox("Seleziona Lotto da Eliminare", list(opzioni_lotti_gest.keys()))
            id_lotto_scelto = opzioni_lotti_gest[label_lotto_scelto]
            lotto_info = report_lotti_df[report_lotti_df['lotto_id'] == id_lotto_scelto].iloc[0]
            
            st.caption(f"Eliminando il lotto **{lotto_info['codice_lotto']}**, i dati storici delle vendite rimarranno salvati nel database.")
            
            if st.button("🗑️ Rimuovi Definitivamente Lotto"):
                elimina_lotto_db(id_lotto_scelto)
                st.success(f"Lotto '{lotto_info['codice_lotto']}' rimosso!")
                st.rerun()

    with st.expander("➕ **Crea Nuovo Prodotto in Anagrafica**", expanded=False):
        with st.form("form_nuovo_prodotto"):
            nome_nuovo = st.text_input("Nome Prodotto", placeholder="Es. Zafferano, Spezia")
            qta_iniziale = st.number_input("Quantità Iniziale (g)", min_value=0.0, value=0.0, step=0.5, format="%.1f")
            costo_u_init = st.number_input("Costo d'Acquisto al grammo (€/g)", min_value=0.1, value=1.0, step=0.5, format="%.2f")
            prezzo_v_init = st.number_input("Prezzo di Vendita al grammo (€/g)", min_value=0.1, value=2.0, step=0.5, format="%.2f")
            scorta_min_init = st.number_input("Scorta Minima Alert (g)", min_value=0.0, value=100.0, step=10.0, format="%.1f")

            if st.form_submit_button("Crea Prodotto"):
                if nome_nuovo.strip() == "":
                    st.error("Inserisci un nome valido.")
                else:
                    try:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO prodotti (nome, unita_misura, valore_mercato_unitario, scorta_minima_g) 
                                VALUES (?, 'g', ?, ?)
                            """, (nome_nuovo.strip(), prezzo_v_init, scorta_min_init))
                            p_id = cursor.lastrowid
                            
                            if qta_iniziale > 0:
                                codice_lotto = f"LOTTO-INIT-{datetime.now().strftime('%Y%m%d')}"
                                cursor.execute("""
                                    INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (p_id, codice_lotto, qta_iniziale, qta_iniziale, costo_u_init, date.today(), date.today()))
                                
                                lotto_id = cursor.lastrowid
                                cursor.execute("""
                                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, note)
                                    VALUES (?, ?, 'CARICO', ?, ?, ?, 'Inizializzazione Prodotto')
                                """, (p_id, lotto_id, qta_iniziale, costo_u_init, qta_iniziale * costo_u_init))
                                
                        st.success(f"Prodotto '{nome_nuovo}' salvato con successo!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Un prodotto con questo nome esiste già.")

# ------------------------------------------
# TAB 4: REPORT & STORICO
# ------------------------------------------
with tab4:
    st.subheader("📜 Registro Storico Transazioni")
    
    movimenti_df = get_movimenti_dettagliati_df()
    
    if movimenti_df.empty:
        st.info("Nessuna transazione registrata nel database.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            prod_filtro = st.multiselect("Filtra per Prodotto", options=movimenti_df['prodotto'].unique(), default=movimenti_df['prodotto'].unique())
        with col_f2:
            tipo_filtro = st.multiselect("Filtra per Tipo Operazione", options=movimenti_df['tipo'].unique(), default=movimenti_df['tipo'].unique())
            
        df_filtrato = movimenti_df[
            (movimenti_df['prodotto'].isin(prod_filtro)) & 
            (movimenti_df['tipo'].isin(tipo_filtro))
        ].copy()

        st.dataframe(
            df_filtrato[[
                'id', 'data', 'prodotto', 'codice_lotto', 'tipo', 'quantita', 'unita_misura',
                'prezzo_unitario', 'ricavo_totale', 'costo_totale', 'margine', 'note'
            ]],
            column_config={
                "id": "ID",
                "data": "Data/Ora",
                "prodotto": "Prodotto",
                "codice_lotto": "Codice Lotto Origine",
                "tipo": "Tipo Operazione",
                "quantita": st.column_config.NumberColumn("Quantità", format="%.1f g"),
                "unita_misura": "U.M.",
                "prezzo_unitario": st.column_config.NumberColumn("Prezzo Unit.", format="€ %.2f"),
                "ricavo_totale": st.column_config.NumberColumn("Ricavo", format="€ %.2f"),
                "costo_totale": st.column_config.NumberColumn("Costo", format="€ %.2f"),
                "margine": st.column_config.NumberColumn("Margine", format="€ %.2f"),
                "note": "Note"
            },
            use_container_width=True,
            hide_index=True
        )

        csv_data = df_filtrato.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Report Storico in CSV",
            data=csv_data,
            file_name=f"report_magazzino_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

        st.markdown("---")
        
        # BLOCCO STORNO CON MARGINI CORRETTI E SPAZIATI
        st.subheader("🔄 Storno Movimento")
        with st.expander("🛠️ **Annulla una transazione specifica**", expanded=False):
            st.write("Selezionando una transazione, l'operazione verrà stornata e la quantità verrà restituita al lotto di origine.")
            
            opzioni_movimenti = {
                f"ID {r['id']} | {r['data']} | {r['prodotto']} (Lotto: {r['codice_lotto']}) | {r['tipo']} ({r['quantita']} g)": r['id']
                for _, r in df_filtrato.iterrows()
            }
            
            mov_selezionato_label = st.selectbox("Seleziona Transazione da Annullare", list(opzioni_movimenti.keys()))
            id_mov_da_stornare = opzioni_movimenti[mov_selezionato_label]
            
            if st.button("❌ Storna / Annulla Questa Transazione"):
                success, msg = storna_movimento(id_mov_da_stornare)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("---")
    
    # BLOCCO RESET FINALE SPAZIATO PER EVITARE TAGLI IN FONDO ALLA PAGINA
    st.subheader("⚙️ Reset Globale Database")
    with st.expander("🚨 **Pulsante di Reset Totale Storico Transazioni**", expanded=False):
        st.warning("Attenzione: l'operazione cancellerà definitivamente tutte le transazioni registrate nello storico.")
        
        if "conferma_reset" not in st.session_state:
            st.session_state["conferma_reset"] = False

        if not st.session_state["conferma_reset"]:
            if st.button("🗑️ Resetta Tutto lo Storico Transazioni"):
                st.session_state["conferma_reset"] = True
                st.rerun()
        else:
            st.error("Sei davvero sicuro di voler cancellare TUTTE le transazioni?")
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                if st.button("✅ Sì, Cancella Definitivamente"):
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM movimenti")
                    st.session_state["conferma_reset"] = False
                    st.success("Storico delle transazioni resettato con successo!")
                    st.rerun()
            with col_res2:
                if st.button("❌ Annulla"):
                    st.session_state["conferma_reset"] = False
                    st.rerun()