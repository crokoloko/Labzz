import base64
import os
import random
import time
from datetime import datetime, date
import pandas as pd
import streamlit as st

from database import (
    init_db, get_connection, get_soglia_esaurimento, get_sospetto, set_sospetto,
    get_prodotti_disponibili_df, get_prodotti_tutti_df, get_lotti_attivi_df,
    get_report_lotti_integrato_df, get_movimenti_dettagliati_df, calcola_stato_magazzino
)
from game_logic import (
    inizializza_pusher_db, get_data_corrente_gioco, e_festivo_o_weekend,
    calcola_grado_reputazione, segna_debito_pagato, genera_offerta_fornitore_casuale,
    genera_cliente_in_negozio, genera_evento_casuale_giorno, esegui_transazione_vendita,
    FASCE_ORARIE, LISTA_NOMI_RAVER
)

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="LaBzz - Free Party Mulino Tycoon",
    page_icon="🌲",
    layout="wide"
)

init_db()
inizializza_pusher_db()

def get_file_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    return None

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

def trigger_effetto_notte():
    js_code = """
    <div id="night-overlay" style="
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: linear-gradient(180deg, #020617 0%, #090d16 50%, #1e1b4b 100%);
        backdrop-filter: blur(0px);
        z-index: 99999;
        opacity: 0;
        pointer-events: none;
        transition: opacity 1.2s ease-in-out, backdrop-filter 1.2s ease-in-out;
        display: flex;
        justify-content: center;
        align-items: center;
        color: #fbbf24;
        font-family: 'Anton', sans-serif;
        font-size: 2.5rem;
        letter-spacing: 3px;
        text-shadow: 0 0 20px rgba(251, 191, 36, 0.6);
    ">🌲 IL BOSCO SI ACCENDE... RAEV COMINCIA 🔊</div>
    <script>
        const overlay = document.getElementById('night-overlay');
        setTimeout(() => {
            overlay.style.opacity = '1';
            overlay.style.backdropFilter = 'blur(12px)';
        }, 50);
        setTimeout(() => {
            overlay.style.opacity = '0';
            overlay.style.backdropFilter = 'blur(0px)';
        }, 2200);
    </script>
    """
    st.components.v1.html(js_code, height=0)

def aggiungi_log(testo):
    st.session_state.log_gioco.insert(0, testo)

# INITIAL STATE
if 'soldi_cassa' not in st.session_state:
    st.session_state.soldi_cassa = 200.0
if 'energia' not in st.session_state:
    st.session_state.energia = 100
if 'giorno' not in st.session_state:
    st.session_state.giorno = 1
if 'giorni_trascorsi_offset' not in st.session_state:
    st.session_state.giorni_trascorsi_offset = 0
if 'indice_fascia_oraria' not in st.session_state:
    st.session_state.indice_fascia_oraria = 0
if 'reputazione' not in st.session_state:
    st.session_state.reputazione = 15
if 'fedelta_clienti' not in st.session_state:
    st.session_state.fedelta_clienti = 10
if 'log_gioco' not in st.session_state:
    st.session_state.log_gioco = ["🪵 **[Giorno 1]** Montati i primi teli e acceso il generatore. I bassi iniziano a vibrare tra gli alberi del mulino. Cassa iniziale: €200."]
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
if 'ultimo_report_bot' not in st.session_state:
    st.session_state.ultimo_report_bot = None
if 'recap_giornata_corrente' not in st.session_state:
    st.session_state.recap_giornata_corrente = None

if st.session_state.cliente_in_negozio is None:
    genera_cliente_in_negozio()

if st.session_state.giorno == 1 and st.session_state.offerta_fornitore is None and st.session_state.max_fornitori_oggi > 0:
    genera_offerta_fornitore_casuale()
    genera_evento_casuale_giorno()

def reset_completo_nuova_partita():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimenti;")
        cursor.execute("DELETE FROM lotti;")
        cursor.execute("DELETE FROM prodotti;")
        cursor.execute("DELETE FROM clienti;")
        cursor.execute("UPDATE pusher SET assunto = 0;")
        
        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario, scorta_minima_g) VALUES ('Skunk', 7.0, 20.0);")
        p_id = cursor.lastrowid
        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, 'MULINO-START', 50.0, 50.0, 2.50, ?, ?);", (p_id, date.today(), date.today()))
        l_id = cursor.lastrowid
        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', 50.0, 125.0, 'Fornitore Furgone', 'Stock Iniziale Mulino')", (p_id, l_id))
    
    set_sospetto(10.0)
    st.session_state.soldi_cassa = 200.0
    st.session_state.giorno = 1
    st.session_state.giorni_trascorsi_offset = 0
    st.session_state.indice_fascia_oraria = 0
    st.session_state.energia = 100
    st.session_state.reputazione = 15
    st.session_state.fedelta_clienti = 10
    st.session_state.log_gioco = ["🪵 **[Giorno 1]** Si ricomincia da capo. Il sound system riprende vita nel bosco. Cassa: €200."]
    st.session_state.offerta_fornitore = None
    st.session_state.cliente_in_negozio = None
    st.session_state.fornitori_visti_oggi = 0
    st.session_state.max_fornitori_oggi = random.choice([0, 1, 2])
    st.session_state.evento_attivo = None
    st.session_state.minigioco_trattativa = False
    st.session_state.ultimo_report_bot = None
    st.session_state.recap_giornata_corrente = None
    if st.session_state.max_fornitori_oggi > 0:
        genera_offerta_fornitore_casuale()
    genera_cliente_in_negozio()
    genera_evento_casuale_giorno()

# ==========================================
# CSS CUSTOM
# ==========================================
sfondo_b64 = get_file_base64("sfondo.jpg")
bg_style = ""
if sfondo_b64:
    bg_style = f"""
    .stApp {{
        background: linear-gradient(rgba(3, 7, 18, 0.75), rgba(3, 7, 18, 0.85)), url("data:image/jpeg;base64,{sfondo_b64}") no-repeat center center fixed !important;
        background-size: cover !important;
    }}
    """
else:
    bg_style = """
    .stApp {
        background-color: #030712 !important;
        background: linear-gradient(135deg, #020617 0%, #064e3b 50%, #0f172a 100%) !important;
    }
    """

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Special+Elite&family=Rajdhani:wght@500;600;700&display=swap');
    {bg_style}
    header[data-testid="stHeader"] {{ display: none !important; }}
    .block-container {{ padding-top: 2rem !important; padding-bottom: 6rem !important; padding-left: 0.8rem !important; padding-right: 0.8rem !important; }}
    .logo-container {{ display: flex !important; justify-content: center !important; align-items: center !important; text-align: center !important; width: 100% !important; margin: 0 auto 1rem auto !important; }}
    .logo-container video {{ display: block !important; margin: 0 auto !important; max-width: 380px !important; width: 100% !important; height: auto !important; border-radius: 8px !important; object-fit: contain !important; }}
    h1, h2, h3, h4, h5, h6 {{ font-family: 'Anton', sans-serif !important; color: #facc15 !important; letter-spacing: 1.5px !important; text-transform: uppercase !important; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.9); }}
    .top-metrics-grid {{ display: grid !important; grid-template-columns: repeat(2, 1fr) !important; gap: 10px !important; width: 100% !important; margin-bottom: 20px !important; }}
    .dashboard-grid {{ display: grid !important; grid-template-columns: repeat(2, 1fr) !important; gap: 12px !important; width: 100% !important; margin-bottom: 25px !important; }}
    .custom-card {{ background: rgba(15, 23, 42, 0.88) !important; backdrop-filter: blur(8px) !important; border-left: 4px solid #10b981 !important; border: 1px solid rgba(255, 255, 255, 0.12) !important; border-radius: 6px !important; padding: 10px 6px !important; display: flex !important; flex-direction: column !important; justify-content: center !important; align-items: center !important; text-align: center !important; width: 100% !important; min-height: 70px !important; box-shadow: 0 8px 24px rgba(0,0,0,0.7); }}
    .card-label {{ color: #9ca3af !important; font-size: 0.62rem !important; font-weight: 700 !important; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 2px !important; }}
    .card-value {{ font-family: 'Anton', sans-serif !important; font-size: 1.05rem !important; letter-spacing: 1px; color: #34d399 !important; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px !important; background-color: transparent !important; border-bottom: none !important; justify-content: center !important; flex-wrap: wrap !important; padding-bottom: 12px; }}
    .stTabs [data-baseweb="tab"] {{ font-family: 'Anton', sans-serif !important; letter-spacing: 1px; background: rgba(15, 23, 42, 0.9) !important; backdrop-filter: blur(6px) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 4px !important; color: #9ca3af !important; font-size: 0.9rem !important; padding: 8px 12px !important; }}
    .stTabs [aria-selected="true"] {{ background: #10b981 !important; color: #030712 !important; border-color: #10b981 !important; }}
    .heist-board {{ background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(10px); border: 2px dashed rgba(16, 185, 129, 0.4); border-radius: 8px; padding: 20px; box-shadow: 0 12px 35px rgba(0,0,0,0.9); margin-bottom: 20px; position: relative; }}
    .heist-title {{ font-family: 'Anton', sans-serif; color: #facc15; font-size: 1.6rem; letter-spacing: 2px; text-transform: uppercase; text-align: center; margin-bottom: 8px; }}
    .heist-quote {{ font-family: 'Special Elite', cursive; color: #e5e7eb; font-size: 0.95rem; text-align: center; background: rgba(0,0,0,0.5); padding: 10px; border-radius: 4px; border-left: 4px solid #10b981; margin-bottom: 15px; }}
</style>
""", unsafe_allow_html=True)

# Logo
video_b64 = get_file_base64("logo.gif.mp4")
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
        st.title("Mulino Underground Tycoon")

# Metriche Header
with get_connection() as conn:
    df_lotti_scorte = pd.read_sql_query("""
        SELECT p.nome, SUM(l.quantita_attuale) as qta 
        FROM lotti l 
        JOIN prodotti p ON l.prodotto_id = p.id 
        WHERE l.quantita_attuale > 0 
        GROUP BY p.nome
    """, conn)

def get_qta_prodotto(nome_prod):
    if not df_lotti_scorte.empty and nome_prod in df_lotti_scorte['nome'].values:
        val = df_lotti_scorte[df_lotti_scorte['nome'] == nome_prod]['qta'].values[0]
        return float(val)
    return 0.0

qta_skunk = get_qta_prodotto("Skunk")
qta_hash = get_qta_prodotto("Hash Dry")
qta_lemon = get_qta_prodotto("Lemon Haze")
qta_frozen = get_qta_prodotto("Frozen Hash")

grado_rep_testo = calcola_grado_reputazione(st.session_state.reputazione)
sospetto_attuale = get_sospetto()

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.markdown(f"""
    <div class="custom-card" style="margin-bottom: 8px;">
        <div class="card-label">💵 Cassa del Mulino</div>
        <div class="card-value">€ {st.session_state.soldi_cassa:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col_m2:
    st.markdown(f"""
    <div class="custom-card" style="margin-bottom: 8px;">
        <div class="card-label">🚨 Attenzione Forestale (Heat)</div>
        <div class="card-value">{sospetto_attuale:.1f} / 100</div>
    </div>
    """, unsafe_allow_html=True)

st.progress(int(sospetto_attuale))

st.markdown(f"""
<div class="top-metrics-grid">
    <div class="custom-card">
        <div class="card-label">📦 Scorte al Mulino</div>
        <div style="font-size: 0.60rem; font-weight: 700; margin-top: 2px; display: flex; justify-content: center; gap: 4px; flex-wrap: wrap; color: #34d399; line-height: 1.2;">
            <span>🌿 {qta_skunk:.1f}g</span> &bull; 
            <span>🧱 {qta_hash:.1f}g</span> &bull; 
            <span>🍋 {qta_lemon:.1f}g</span> &bull; 
            <span>❄️ {qta_frozen:.1f}g</span>
        </div>
    </div>
    <div class="custom-card">
        <div class="card-label">📅 Giorno nel Bosco</div>
        <div class="card-value">Giorno {st.session_state.giorno}</div>
    </div>
    <div class="custom-card">
        <div class="card-label">⚡ Energia Fisica</div>
        <div class="card-value">{st.session_state.energia}%</div>
    </div>
    <div class="custom-card">
        <div class="card-label">⭐ Rango nel Raduno</div>
        <div style="font-size: 0.75rem; font-family: 'Anton', sans-serif; color: #34d399;">{grado_rep_testo}</div>
    </div>
</div>
""", unsafe_allow_html=True)

data_oggi = get_data_corrente_gioco()
is_fest, desc_fest = e_festivo_o_weekend(data_oggi)
data_formattata = data_oggi.strftime("%d %B %Y")

with st.container(border=True):
    col_n1, col_n2, col_n3 = st.columns([1, 2, 1])
    with col_n2:
        if st.button("🌲 Avanza Giorno (Alba sul Fiume)", use_container_width=True):
            set_sospetto(get_sospetto() - 8.0)
            trigger_effetto_notte()
            st.session_state.giorno += 1
            st.session_state.giorni_trascorsi_offset += 1
            st.session_state.indice_fascia_oraria = 0
            st.session_state.energia = 100
            
            st.session_state.offerta_fornitore = None
            st.session_state.fornitori_visti_oggi = 0
            st.session_state.max_fornitori_oggi = random.choice([0, 1, 1, 2])
            st.session_state.minigioco_trattativa = False
            st.session_state.ultimo_report_bot = None
            st.session_state.recap_giornata_corrente = None
            
            if st.session_state.max_fornitori_oggi > 0 and random.random() < 0.60:
                genera_offerta_fornitore_casuale()
                
            genera_cliente_in_negozio()
            genera_evento_casuale_giorno()
            
            nuovo_giorno = st.session_state.giorno
            aggiungi_log(f"🌅 **[Giorno {nuovo_giorno}]** Il sole sorge sul fiume. Nuovi furgoni nel parcheggio e carovane pronte ad accendere i sound system.")
            st.rerun()

    st.markdown(f"""
        <div style="text-align: center; font-family: 'Rajdhani', sans-serif; font-size: 0.78rem; font-weight: 500; color: #9ca3af; margin-top: 6px; letter-spacing: 1px;">
            {data_formattata} &bull; <span style="color: #34d399;">{desc_fest}</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Eventi attivi
if st.session_state.evento_attivo:
    ev = st.session_state.evento_attivo
    with st.container(border=True):
        st.markdown(f"### {ev['titolo']}")
        st.write(ev['testo'])
        
        if ev['tipo'] == 'polizia':
            col_ev1, col_ev2, col_ev3 = st.columns(3)
            with col_ev1:
                if st.button("💰 Corrompi Guardia Forestale (€50)", use_container_width=True):
                    if st.session_state.soldi_cassa >= 50.0:
                        st.session_state.soldi_cassa -= 50.0
                        set_sospetto(get_sospetto() - 35.0)
                        st.success("Accordo trovato lungo il fiume! La pattuglia si allontana.")
                        g_n = st.session_state.giorno
                        aggiungi_log(f"🚓 **[Giorno {g_n}]** Pagata tangente di €50 alla guardia forestale lungo il sentiero. La situazione si calma.")
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error("Fondi insufficienti per corrompere la pattuglia!")
            with col_ev2:
                if st.button("🏃 Nascondi Scorte tra gli Alberi", use_container_width=True):
                    if random.random() < (0.60 - (get_sospetto() / 200)):
                        st.success("Sei sgusciato tra i sentieri bui del bosco senza farti notare!")
                        set_sospetto(get_sospetto() - 15.0)
                    else:
                        st.warning("La forestale ha perquisito un furgone! Sequestrato materiale e scorte!")
                        st.session_state.soldi_cassa = max(0.0, st.session_state.soldi_cassa - 80.0)
                        with get_connection() as conn:
                            conn.execute("UPDATE lotti SET quantita_attuale = MAX(0.0, quantita_attuale - 10.0) WHERE quantita_attuale > 0 LIMIT 3")
                        set_sospetto(10.0)
                    st.session_state.evento_attivo = None
                    st.rerun()
            with col_ev3:
                if st.button("🔇 Abbassa i Sound System", use_container_width=True):
                    set_sospetto(get_sospetto() - 25.0)
                    st.info("Musica a volume basso per oggi per evitare rogne.")
                    st.session_state.evento_attivo = None
                    st.rerun()

        elif ev['tipo'] == 'vip':
            col_vip1, col_vip2 = st.columns(2)
            with col_vip1:
                if st.button("✅ ACCETTA ORDINE DAL PALCO", use_container_width=True):
                    with get_connection() as conn:
                        qta_disp_vip = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(ev['prodotto_id'],)).iloc[0, 0]
                    qta_disp_vip = float(qta_disp_vip) if qta_disp_vip else 0.0
                    
                    if qta_disp_vip >= ev['quantita']:
                        cli_vip_obj = {"nome": "Runner Palco Centrale", "prodotto_id": ev['prodotto_id'], "prodotto_nome": ev['prodotto_nome'], "quantita_richiesta": ev['quantita']}
                        esegui_transazione_vendita(cli_vip_obj, ev['prezzo_offerto'], "Subito", callback_log=aggiungi_log)
                        spara_fuochi_d_artificio()
                        st.success(f"🎉 Rifornimento palco completato! Incasso: €{ev['quantita'] * ev['prezzo_offerto']:.2f}")
                        st.session_state.reputazione = min(100, st.session_state.reputazione + 5)
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error("Scorte insufficienti al mulino per questo ordine!")
            with col_vip2:
                if st.button("❌ Rifiuta", use_container_width=True):
                    st.session_state.evento_attivo = None
                    st.rerun()

        elif ev['tipo'] == 'festival':
            if st.button("🎉 Ottimo! Goditi il Raduno", use_container_width=True):
                st.session_state.evento_attivo = None
                st.rerun()

        else:
            if st.button("🛡️ Allontana i Guastafeste", use_container_width=True):
                st.success("Li hai cacciati via verso i sentieri secondari senza danni.")
                st.session_state.evento_attivo = None
                st.rerun()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏕️ Base Mulino", 
    "👥 Crew / Pusher",
    "📊 Dashboard", 
    "🚚 Parcheggio Furgoni",
    "📈 Statistiche",
    "📜 Mappa & Obiettivi"
])

with tab1:
    col_cassa, col_ledger = st.columns([1.2, 1])
    with col_cassa:
        st.subheader("🏕️ Spaccio al Campeggio / Mulino")
        tipo_operazione = st.radio("Seleziona Attività", ["Incontra Raver (Manuale)", "Automazione Turni Sound System", "XME (Energia Personale)"], horizontal=True)
        
        if tipo_operazione == "Incontra Raver (Manuale)":
            st.markdown("##### ⛺ Raver al Banco del Mulino")
            cli_att = st.session_state.cliente_in_negozio
            if cli_att:
                with st.container(border=True):
                    st.markdown(f"### **{cli_att['nome']}** (Dal Bosco)")
                    st.write(f"• **Richiesta:** ⭐ **{cli_att['prodotto_nome']}** ({cli_att['quantita_richiesta']} g)")
                    
                    with get_connection() as conn:
                        qta_disp_query = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(cli_att['prodotto_id'],)).iloc[0, 0]
                        
                    qta_disp_tot = float(qta_disp_query) if (qta_disp_query is not None and not pd.isna(qta_disp_query)) else 0.0

                    if qta_disp_tot < cli_att['quantita_richiesta']:
                        st.error(f"❌ Scorte insufficienti al mulino! (Disponibili: {qta_disp_tot:.1f}g)")
                        if st.button("👋 Manda via il Raver", use_container_width=True):
                            st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 1)
                            genera_cliente_in_negozio()
                            st.rerun()
                    else:
                        prezzo_proposto = st.number_input("Prezzo al Grammo (€/g)", min_value=0.5, value=float(cli_att['budget_max_g']), step=0.5, format="%.2f")
                        totale_proposto = prezzo_proposto * cli_att['quantita_richiesta']
                        st.write(f"**Totale:** € {totale_proposto:.2f}")

                        tipo_pagamento = st.radio("Pagamento", ["Subito", "Dopo (Credito / Ti pago al prossimo sound system)"], horizontal=True, key="pag_init")
                        pagamento_db = "Subito" if "Subito" in tipo_pagamento else "Dopo (Credito)"

                        if st.button("🤝 Cedi Merce", use_container_width=True):
                            esegui_transazione_vendita(cli_att, prezzo_proposto, pagamento_db, callback_log=aggiungi_log)
                            spara_fuochi_d_artificio()
                            genera_cliente_in_negozio()
                            st.rerun()

        elif tipo_operazione == "Automazione Turni Sound System":
            idx_corrente = st.session_state.indice_fascia_oraria
            if idx_corrente >= len(FASCE_ORARIE):
                st.warning("⚠️ Hai completato tutte e 5 le fasce orarie della giornata nel bosco! Clicca su **'🌲 Avanza Giorno (Alba sul Fiume)'** in cima per continuare.")
                with st.container(border=True):
                    st.markdown("### 📊 RECAP TOTALE GIORNATA NEL BOSCO (FINE TURNI)")
                    recap_data = st.session_state.get('recap_giornata_corrente')
                    if recap_data:
                        col_r1, col_r2 = st.columns(2)
                        col_r1.metric("💵 Incasso Totale Giorno", f"€ {recap_data['incasso_totale']:,.2f}")
                        col_r2.metric("📈 Margine Netto Giorno", f"€ {recap_data['margine_totale']:,.2f}")
                        st.write(f"• **Raver Unici Serviti:** 👥 {recap_data['clienti_serviti']} (Transazioni totali: {recap_data['transazioni_totali']})")
                        st.markdown("##### 📦 Quantità Distribuite per Prodotto:")
                        for prod_n, q_v in recap_data['prodotti_distribuiti'].items():
                            st.write(f"&bull; **{prod_n}**: {q_v:.1f} g")
                    else:
                        st.info("Nessun dato di recap registrato per questa sessione.")
            else:
                st.markdown(f"##### 🔊 Automazione Spaccio Sound System (Autonoma)")
                st.info(f"Fascia oraria corrente: **{FASCE_ORARIE[idx_corrente]}** ({idx_corrente + 1} di 5)")
                strategia_bot = st.selectbox("Strategia Crew", ["Onesta / Prezzo Popolare", "Aggressiva (+20%)", "Solidale (-15%)"])

                with get_connection() as conn:
                    pusher_assunti = pd.read_sql_query("SELECT * FROM pusher WHERE assunto = 1", conn)

                if st.button("🚀 AVVIA CICLO AUTOMATICO GIORNATA (5 Turni)", use_container_width=True):
                    if st.session_state.energia < 20:
                        st.error("Sei troppo stanco per avviare il ciclo automatico! Riposa.")
                    else:
                        placeholder_progresso = st.empty()
                        incasso_totale_giorno = 0.0
                        margine_totale_giorno = 0.0
                        clienti_serviti_set = set()
                        transazioni_totali_giorno = 0
                        prodotti_distribuiti_giorno = {}
                        
                        while st.session_state.indice_fascia_oraria < len(FASCE_ORARIE):
                            idx_c = st.session_state.indice_fascia_oraria
                            fascia_nome = FASCE_ORARIE[idx_c]
                            placeholder_progresso.markdown(f"⏳ **Esecuzione in corso:** {fascia_nome}...")
                            
                            st.session_state.energia = max(0, st.session_state.energia - 10)
                            prodotti_tutti = get_prodotti_tutti_df()
                            
                            if not prodotti_tutti.empty:
                                is_f, _ = e_festivo_o_weekend(get_data_corrente_gioco())
                                moltiplicatore_festivo = 1.35 if is_f else 1.0
                                base_clienti = random.randint(3, 6) if idx_c >= 3 else random.randint(2, 4)
                                bonus_efficienza_totale = pusher_assunti['efficienza'].sum() if not pusher_assunti.empty else 0.0
                                
                                num_clienti_tot = int((base_clienti + int(st.session_state.fedelta_clienti / 25) + int(bonus_efficienza_totale * 3)) * moltiplicatore_festivo)
                                nomi_turno_disponibili = random.sample(LISTA_NOMI_RAVER, min(len(LISTA_NOMI_RAVER), max(4, num_clienti_tot + 2)))
                                
                                vendite_ok = 0
                                incasso_turno = 0.0
                                vendite_prodotti_turno = {}
                                
                                for i in range(num_clienti_tot):
                                    if not nomi_turno_disponibili: break
                                    cli_nome = nomi_turno_disponibili.pop(0)
                                    prod_req = prodotti_tutti.sample(n=1).iloc[0]
                                    p_id = int(prod_req['id'])
                                    p_nome = prod_req['nome']
                                    val_m = float(prod_req['valore_mercato_unitario'])
                                    
                                    with get_connection() as conn:
                                        cursor = conn.cursor()
                                        cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", (p_id,))
                                        lotti = cursor.fetchall()
                                        if not lotti: continue
                                        
                                        prezzo_bot = val_m * 1.25 if "Aggressiva" in strategia_bot else (val_m * 0.85 if "Solidale" in strategia_bot else val_m)
                                        if st.session_state.evento_attivo and st.session_state.evento_attivo['tipo'] == 'festival':
                                            prezzo_bot *= 1.2
                                            
                                        qta_req = float(random.choices([1, 2, 5, 10, 15, 20], weights=[35, 30, 20, 10, 3, 2], k=1)[0])
                                        qta_req = min(lotti[0][1], qta_req)
                                        if qta_req <= 0: continue
                                        
                                        l_id, l_qta, l_costo = lotti[0]
                                        cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale - ? WHERE id = ?", (qta_req, l_id))
                                        ricavo = qta_req * prezzo_bot
                                        margine = ricavo - (qta_req * l_costo)
                                        
                                        if not pusher_assunti.empty:
                                            pusher_assegnato = pusher_assunti.sample(n=1).iloc[0]
                                            quota_pusher = float(pusher_assegnato['quota_trattenuta'])
                                            guadagno_pusher = ricavo * quota_pusher
                                            guadagno_boss = ricavo - guadagno_pusher
                                            note_movimento = f"Spaccio tramite Pusher ({pusher_assegnato['nome']} - Trattenuta {quota_pusher*100:.0f}%, Quota Pusher: €{guadagno_pusher:.2f})"
                                        else:
                                            guadagno_boss = ricavo
                                            note_movimento = f"Spaccio diretto gestito al Mulino"
                                        
                                        cursor.execute("""
                                            INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note)
                                            VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, 'Subito', ?)
                                        """, (p_id, l_id, qta_req, prezzo_bot, ricavo, qta_req * l_costo, margine, cli_nome, note_movimento))
                                        
                                        st.session_state.soldi_cassa += guadagno_boss
                                        incasso_turno += ricavo
                                        vendite_ok += 1
                                        vendite_prodotti_turno[p_nome] = vendite_prodotti_turno.get(p_nome, 0.0) + qta_req

                                        incasso_totale_giorno += ricavo
                                        margine_totale_giorno += margine
                                        clienti_serviti_set.add(cli_nome)
                                        transazioni_totali_giorno += 1
                                        prodotti_distribuiti_giorno[p_nome] = prodotti_distribuiti_giorno.get(p_nome, 0.0) + qta_req

                                if vendite_ok > 0:
                                    st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 4)
                                    set_sospetto(get_sospetto() + (vendite_ok * 0.7))
                                
                                st.session_state.ultimo_report_bot = {
                                    "fascia": fascia_nome,
                                    "vendite_ok": vendite_ok,
                                    "incasso": incasso_turno,
                                    "vendite_prodotti": vendite_prodotti_turno
                                }

                            st.session_state.indice_fascia_oraria += 1
                            time.sleep(2.0)

                        st.session_state.recap_giornata_corrente = {
                            "incasso_totale": incasso_totale_giorno,
                            "margine_totale": margine_totale_giorno,
                            "clienti_serviti": len(clienti_serviti_set),
                            "transazioni_totali": transazioni_totali_giorno,
                            "prodotti_distribuiti": prodotti_distribuiti_giorno
                        }
                        
                        g_n = st.session_state.giorno
                        aggiungi_log(f"🔊 **[Giorno {g_n}]** Completati i turni di sound system. Incassati €{incasso_totale_giorno:,.2f} con {len(clienti_serviti_set)} raver unici serviti tra le tende.")
                        
                        placeholder_progresso.success("🎉 Tutti i turni della giornata sono stati completati con successo!")
                        time.sleep(1)
                        st.rerun()

            if st.session_state.ultimo_report_bot and st.session_state.indice_fascia_oraria < len(FASCE_ORARIE):
                rep_bot = st.session_state.ultimo_report_bot
                with st.container(border=True):
                    st.markdown(f"##### 📋 Report Ultima Fascia: {rep_bot['fascia']}")
                    col_rb1, col_rb2 = st.columns(2)
                    col_rb1.metric("💵 Incasso Fascia", f"€ {rep_bot['incasso']:,.2f}")
                    col_rb2.metric("👥 Raver Serviti", rep_bot['vendite_ok'])
                    for prod_n, q_v in rep_bot['vendite_prodotti'].items():
                        st.write(f"&bull; **{prod_n}**: {q_v:.1f} g")

        else:
            st.markdown("##### 🧪 Ricarica Personale tra gli Alberi (+30% Energia)")
            lotti_df = get_lotti_attivi_df()
            if not lotti_df.empty:
                with st.form("form_xme"):
                    opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                    lotto_sel = st.selectbox("Lotto", list(opzioni_lotto.keys()))
                    lotto_id = opzioni_lotto[lotto_sel]
                    qta_xme = st.number_input("Quantità (g)", min_value=0.5, value=5.0, step=0.5)

                    if st.form_submit_button("Usa per Ricarica"):
                        lotto_row = lotti_df[lotti_df['id'] == lotto_id].iloc[0]
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            nuova_q = float(lotto_row['quantita_attuale']) - qta_xme
                            p_id = int(get_prodotti_tutti_df()[get_prodotti_tutti_df()['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                            cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_q, lotto_id))
                            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, margine, cliente, note) VALUES (?, ?, 'XME', ?, ?, ?, 'Ricarica', 'Consumo nel Bosco')", (p_id, lotto_id, qta_xme, qta_xme * float(lotto_row['costo_acquisto_unitario']), -qta_xme * float(lotto_row['costo_acquisto_unitario'])))
                        st.session_state.energia = min(100, st.session_state.energia + 30)
                        st.rerun()

    with col_ledger:
        st.subheader("📜 Cronaca del Bosco")
        with st.container(border=True):
            for log in st.session_state.log_gioco[:10]:
                st.markdown(log)
                st.markdown("---")

with tab2:
    st.subheader("👥 Gestione Crew nel Bosco (A Percentuale)")
    with get_connection() as conn:
        pusher_df = pd.read_sql_query("SELECT * FROM pusher", conn)
    for _, p in pusher_df.iterrows():
        with st.container(border=True):
            col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
            col_p1.markdown(f"### **{p['nome']}**")
            col_p2.write(f"• **Trattiene:** {p['quota_trattenuta']*100:.0f}%\n• **Efficienza:** +{p['efficienza']*100:.0f}%")
            if bool(p['assunto']):
                if col_p3.button("Allontana", key=f"lic_{p['id']}"):
                    with get_connection() as conn:
                        conn.execute("UPDATE pusher SET assunto = 0 WHERE id = ?", (p['id'],))
                    st.rerun()
            else:
                if col_p3.button("Ingaggia", key=f"ass_{p['id']}"):
                    with get_connection() as conn:
                        conn.execute("UPDATE pusher SET assunto = 1 WHERE id = ?", (p['id'],))
                    st.rerun()

with tab3:
    st.subheader("📊 Dashboard Economica del Mulino")
    df_stato_disp = calcola_stato_magazzino(solo_disponibili=True)
    movimenti_df = get_movimenti_dettagliati_df()
    if not df_stato_disp.empty or not movimenti_df.empty:
        val_costo = df_stato_disp['valore_totale_costo'].sum() if not df_stato_disp.empty else 0
        val_mercato = df_stato_disp['valore_totale_mercato'].sum() if not df_stato_disp.empty else 0
        incasso_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['incasso'].sum() if not movimenti_df.empty else 0
        margine_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['margine'].sum() if not movimenti_df.empty else 0
        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="custom-card"><div class="card-label">Valore Scorte (Costo)</div><div class="card-value">€ {val_costo:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Valore Scorte (Mercato)</div><div class="card-value">€ {val_mercato:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Incasso Totale</div><div class="card-value">€ {incasso_tot:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Margine Netto</div><div class="card-value">€ {margine_tot:,.2f}</div></div>
        </div>
        """, unsafe_allow_html=True)

with tab4:
    st.subheader("🚚 Parcheggio Furgoni & Fornitori Nomadi")
    if st.session_state.offerta_fornitore:
        off = st.session_state.offerta_fornitore
        costo_tot = off['costo_totale']
        ha_soldi = st.session_state.soldi_cassa >= costo_tot
        st.markdown(f"""
        <div class="heist-board">
            <div class="heist-title">🎯 CONTATTO NEL FANGO: {off['fornitore_nome'].upper()}</div>
            <div class="heist-quote">{off['fornitore_frase']}</div>
            <div style="text-align: center; margin-top: 15px;">INVESTIMENTO: <strong style="color: #facc15;">€ {costo_tot:,.2f}</strong></div>
        </div>
        """, unsafe_allow_html=True)
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("💼 COMPRA INTERO STOCK", use_container_width=True, disabled=not ha_soldi):
                st.session_state.soldi_cassa -= costo_tot
                set_sospetto(get_sospetto() + 6.0)
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR IGNORE INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (off['prodotto_nome'], off['valore_mercato_suggerito']))
                    p_id = cursor.execute("SELECT id FROM prodotti WHERE nome = ?", (off['prodotto_nome'],)).fetchone()[0]
                    cursor.execute("""
                        INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (p_id, off['codice_lotto'], off['quantita'], off['quantita'], off['costo_unitario'], date.today(), date.today()))
                
                g_n = st.session_state.giorno
                aggiungi_log(f"📦 **[Giorno {g_n}]** Chiuso affare con {off['fornitore_nome']}: caricati **{off['quantita']}g** di *{off['prodotto_nome']}* al mulino.")
                st.session_state.offerta_fornitore = None
                st.rerun()
        with col_b2:
            if st.button("❌ Rimanda via il Furgone", use_container_width=True):
                st.session_state.offerta_fornitore = None
                st.rerun()
    else:
        fornitori_rimasti = st.session_state.max_fornitori_oggi - st.session_state.fornitori_visti_oggi
        if fornitori_rimasti > 0:
            if st.button("📞 Cerca Furgone nel Parcheggio", use_container_width=True):
                genera_offerta_fornitore_casuale()
                st.rerun()
        else:
            st.warning("Nessun altro furgone disponibile nel parcheggio oggi.")

with tab5:
    st.subheader("📈 Crediti Raver tra le Tende")
    movimenti_df = get_movimenti_dettagliati_df()
    if not movimenti_df.empty:
        clienti_debito = movimenti_df[(movimenti_df['tipo'] == 'VENDITA') & (movimenti_df['stato_pagamento'] == 'Dopo (Credito)')]
        if not clienti_debito.empty:
            debito_per_cliente = clienti_debito.groupby('cliente')['incasso'].sum().reset_index()
            for _, r_d in debito_per_cliente.iterrows():
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"**{r_d['cliente']}**: € {r_d['incasso']:,.2f}")
                if col_d2.button("Incassa", key=f"s_{r_d['cliente']}"):
                    segna_debito_pagato(r_d['cliente'])
                    st.rerun()

with tab6:
    st.subheader("🎯 Obiettivi del Raduno & Condizioni di Vittoria")
    movimenti_df = get_movimenti_dettagliati_df()
    utile_totale = movimenti_df['margine'].sum() if not movimenti_df.empty else 0.0
    st.progress(min(1.0, utile_totale / 10000.0))
    st.write(f"• **Utile Netto Attuale:** € {utile_totale:,.2f} / € 10,000.00 obiettivo festival")
    if st.button("💥 Reset Totale del Mulino"):
        reset_completo_nuova_partita()
        st.rerun()
