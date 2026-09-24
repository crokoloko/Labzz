import sqlite3
from datetime import datetime, date
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Labzz",
    page_icon="📦",
    layout="wide"
)

DB_NAME = "magazzino.db"

# ==========================================
# GESTIONE DATABASE SQLITE
# ==========================================
def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    """Inizializza le tabelle del database se non esistono."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Anagrafica prodotti
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prodotti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        unita_misura TEXT NOT NULL,
        valore_mercato_unitario REAL DEFAULT 0
    )
    """)
    
    # Registro lotti di carico
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lotti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prodotto_id INTEGER NOT NULL,
        codice_lotto TEXT NOT NULL,
        quantita_iniziale REAL NOT NULL,
        quantita_attuale REAL NOT NULL,
        costo_acquisto_unitario REAL NOT NULL,
        data_carico DATE NOT NULL,
        data_scadenza DATE,
        FOREIGN KEY (prodotto_id) REFERENCES prodotti (id)
    )
    """)
    
    # Registro movimenti (carico, vendita, scarto)
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
        FOREIGN KEY (prodotto_id) REFERENCES prodotti (id),
        FOREIGN KEY (lotto_id) REFERENCES lotti (id)
    )
    """)
    
    # Popola prodotti base se tabella vuota
    cursor.execute("SELECT COUNT(*) FROM prodotti")
    if cursor.fetchone()[0] == 0:
        prodotti_iniziali = [
            ("Farina", "kg", 1.50),
            ("Zucchero", "kg", 1.20),
            ("Cioccolata", "kg", 8.50),
            ("Fieno", "tonnellate", 180.00)
        ]
        cursor.executemany("""
            INSERT INTO prodotti (nome, unita_misura, valore_mercato_unitario)
            VALUES (?, ?, ?)
        """, prodotti_iniziali)
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# FUNZIONI UTILITY DATI
# ==========================================
def get_prodotti_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", conn)
    conn.close()
    return df

def get_lotti_df():
    conn = get_connection()
    query = """
        SELECT l.id, p.nome AS prodotto, l.codice_lotto, l.quantita_attuale, 
               p.unita_misura, l.costo_acquisto_unitario, l.data_carico, l.data_scadenza
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        WHERE l.quantita_attuale > 0
        ORDER BY l.data_scadenza ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_movimenti_df():
    conn = get_connection()
    query = """
        SELECT m.id, m.data, p.nome AS prodotto, m.tipo, m.quantita, p.unita_misura,
               m.prezzo_unitario, m.ricavo_totale, m.costo_totale, m.margine, m.note
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        ORDER BY m.data DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def calcola_stato_magazzino():
    conn = get_connection()
    prodotti_df = pd.read_sql_query("SELECT * FROM prodotti", conn)
    lotti_df = pd.read_sql_query("SELECT * FROM lotti WHERE quantita_attuale > 0", conn)
    movimenti_df = pd.read_sql_query("SELECT * FROM movimenti", conn)
    conn.close()

    risultati = []
    
    for _, prod in prodotti_df.iterrows():
        p_id = prod['id']
        lotti_prod = lotti_df[lotti_df['prodotto_id'] == p_id]
        
        qta_totale = lotti_prod['quantita_attuale'].sum()
        valore_costo_totale = (lotti_prod['quantita_attuale'] * lotti_prod['costo_acquisto_unitario']).sum()
        costo_medio_ponderato = (valore_costo_totale / qta_totale) if qta_totale > 0 else 0
        valore_mercato_totale = qta_totale * prod['valore_mercato_unitario']
        
        vendite = movimenti_df[(movimenti_df['prodotto_id'] == p_id) & (movimenti_df['tipo'] == 'VENDITA')]
        qta_venduta = vendite['quantita'].sum()
        incasso_totale = vendite['ricavo_totale'].sum()
        margine_totale = vendite['margine'].sum()

        risultati.append({
            'prodotto_id': p_id,
            'prodotto': prod['nome'],
            'unita_misura': prod['unita_misura'],
            'qta_disponibile': qta_totale,
            'costo_medio_ponderato': costo_medio_ponderato,
            'valore_mercato_unitario': prod['valore_mercato_unitario'],
            'valore_totale_costo': valore_costo_totale,
            'valore_totale_mercato': valore_mercato_totale,
            'qta_venduta': qta_venduta,
            'incasso_totale': incasso_totale,
            'margine_totale': margine_totale
        })

    return pd.DataFrame(risultati)

# ==========================================
# INTERFACCIA UTENTE (STREAMLIT)
# ==========================================
st.title("📦 Labzz")

# Sidebar - Configurazione Prezzi di Mercato
with st.sidebar:
    st.header("⚙️ Prezzi di Mercato")
    prodotti_df = get_prodotti_df()
    prod_scelto = st.selectbox("Seleziona Prodotto", prodotti_df['nome'].tolist())
    
    prod_row = prodotti_df[prodotti_df['nome'] == prod_scelto].iloc[0]
    
    with st.form("form_config_prodotto"):
        st.subheader(f"Modifica Prezzo {prod_scelto}")
        nuovo_val_mercato = st.number_input("Prezzo / Valore Unitario (€)", value=float(prod_row['valore_mercato_unitario']), step=0.1)
        
        if st.form_submit_button("Aggiorna Prezzo"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE prodotti 
                SET valore_mercato_unitario = ?
                WHERE id = ?
            """, (nuovo_val_mercato, prod_row['id']))
            conn.commit()
            conn.close()
            st.success("Prezzo aggiornato!")
            st.rerun()

# Tabs principali
tab1, tab2, tab3, tab4 = st.tabs([
    "💸 Cassa & Movimenti", 
    "📊 Dashboard & KPI", 
    "📋 Gestione Stock", 
    "📜 Report & Storico"
])

# ------------------------------------------
# TAB 1: CASSA & REGISTRA MOVIMENTI (PRIMA PAGINA)
# ------------------------------------------
with tab1:
    st.subheader("Cassa Operativa")
    
    tipo_operazione = st.radio("Seleziona Operazione", ["Vendita", "Acquisto", "Registra Scarto"], horizontal=True)
    prodotti_df = get_prodotti_df()
    
    # 1. VENDITA
    if tipo_operazione == "Vendita":
        prod_nome = st.selectbox("Seleziona Prodotto da Vendere", prodotti_df['nome'].tolist())
        prod_row = prodotti_df[prodotti_df['nome'] == prod_nome].iloc[0]
        p_id = int(prod_row['id'])
        
        conn = get_connection()
        query_lotti = "SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_scadenza ASC"
        lotti_disponibili = pd.read_sql_query(query_lotti, conn, params=(p_id,))
        conn.close()

        if lotti_disponibili.empty:
            st.error("⚠️ Nessun lotto disponibile in magazzino per questo prodotto.")
        else:
            qta_tot_disp = lotti_disponibili['quantita_attuale'].sum()
            st.info(f"Disponibilità in magazzino per **{prod_nome}**: **{qta_tot_disp:.2f} {prod_row['unita_misura']}**")
            
            with st.form("form_vendita"):
                st.markdown("##### Registra Vendita")
                col1, col2 = st.columns(2)
                
                with col1:
                    quantita_vendita = st.number_input("Quantità da Vendere", min_value=0.01, value=1.0, step=1.0)
                    prezzo_vendita_unitario = st.number_input("Prezzo Unitario (€)", min_value=0.01, value=float(prod_row['valore_mercato_unitario']), step=0.1)
                
                with col2:
                    note = st.text_input("Note (Opzionale)")

                if st.form_submit_button("Vendita"):
                    if quantita_vendita > qta_tot_disp:
                        st.error(f"Quantità inserita ({quantita_vendita}) superiore alla disponibilità ({qta_tot_disp}).")
                    else:
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        qta_rimanente = quantita_vendita
                        costo_totale_acquisto = 0.0
                        
                        for _, lotto in lotti_disponibili.iterrows():
                            if qta_rimanente <= 0:
                                break
                            
                            l_id = lotto['id']
                            qta_lotto = lotto['quantita_attuale']
                            costo_u = lotto['costo_acquisto_unitario']
                            
                            if qta_lotto <= qta_rimanente:
                                prelievo = qta_lotto
                                qta_rimanente -= qta_lotto
                                nuova_qta = 0.0
                            else:
                                prelievo = qta_rimanente
                                nuova_qta = qta_lotto - qta_rimanente
                                qta_rimanente = 0.0
                            
                            costo_totale_acquisto += prelievo * costo_u
                            cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, l_id))
                        
                        ricavo_totale = quantita_vendita * prezzo_vendita_unitario
                        margine = ricavo_totale - costo_totale_acquisto
                        
                        cursor.execute("""
                            INSERT INTO movimenti (prodotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, note)
                            VALUES (?, 'VENDITA', ?, ?, ?, ?, ?, ?)
                        """, (p_id, quantita_vendita, prezzo_vendita_unitario, ricavo_totale, costo_totale_acquisto, margine, note))
                        
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Vendita registrata! Incasso: €{ricavo_totale:,.2f} | Margine: €{margine:,.2f}")
                        st.rerun()

    # 2. ACQUISTO
    elif tipo_operazione == "Acquisto":
        with st.form("form_carico"):
            st.markdown("##### Registra Acquisto")
            col1, col2 = st.columns(2)
            
            with col1:
                prod_nome = st.selectbox("Prodotto", prodotti_df['nome'].tolist())
                quantita = st.number_input("Quantità Acquistata", min_value=0.01, value=10.0, step=1.0)
                costo_unitario = st.number_input("Costo Unitario (€)", min_value=0.01, value=1.0, step=0.1)
                
            with col2:
                codice_lotto = st.text_input("Codice Lotto", value=f"LOTTO-{datetime.now().strftime('%Y%m%d-%H%M')}")
                data_scadenza = st.date_input("Data di Scadenza", value=date.today())
                note = st.text_input("Note Aggiuntive")

            if st.form_submit_button("Acquisto"):
                prod_row = prodotti_df[prodotti_df['nome'] == prod_nome].iloc[0]
                p_id = int(prod_row['id'])
                
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico, data_scadenza)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (p_id, codice_lotto, quantita, quantita, costo_unitario, date.today(), data_scadenza))
                
                lotto_id = cursor.lastrowid
                costo_totale = quantita * costo_unitario
                
                cursor.execute("""
                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, note)
                    VALUES (?, ?, 'CARICO', ?, ?, ?, ?)
                """, (p_id, lotto_id, quantita, costo_unitario, costo_totale, note))
                
                conn.commit()
                conn.close()
                st.success(f"✅ Acquisto registrato col lotto {codice_lotto}!")
                st.rerun()

    # 3. REGISTRA SCARTO
    elif tipo_operazione == "Registra Scarto":
        lotti_df = get_lotti_df()
        
        if lotti_df.empty:
            st.error("Nessun lotto disponibile da cui scaricare scarti.")
        else:
            with st.form("form_scarto"):
                st.markdown("##### Registra Calo Peso / Deterioramento")
                
                opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']} {r['unita_misura']})": r['id'] for _, r in lotti_df.iterrows()}
                lotto_selezionato_label = st.selectbox("Seleziona Lotto da Scaricare", list(opzioni_lotto.keys()))
                lotto_id_scelto = opzioni_lotto[lotto_selezionato_label]
                
                lotto_row = lotti_df[lotti_df['id'] == lotto_id_scelto].iloc[0]
                
                qta_scarto = st.number_input("Quantità da Scartare", min_value=0.01, max_value=float(lotto_row['quantita_attuale']), value=1.0, step=0.5)
                motivo = st.text_input("Motivazione Scarto", placeholder="Es. Calo peso fieno, Umidità, Sacchetto rotto")

                if st.form_submit_button("Conferma Scarto"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    nuova_qta = lotto_row['quantita_attuale'] - qta_scarto
                    costo_perdita = qta_scarto * lotto_row['costo_acquisto_unitario']
                    
                    prodotti_df = get_prodotti_df()
                    p_id = int(prodotti_df[prodotti_df['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                    
                    cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, lotto_id_scelto))
                    
                    cursor.execute("""
                        INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, margine, note)
                        VALUES (?, ?, 'SCARTO', ?, 0, ?, ?, ?)
                    """, (p_id, lotto_id_scelto, qta_scarto, costo_perdita, -costo_perdita, f"SCARTO: {motivo}"))
                    
                    conn.commit()
                    conn.close()
                    st.warning(f"Scarto registrato! Perdita generata: €{costo_perdita:,.2f}")
                    st.rerun()

# ------------------------------------------
# TAB 2: DASHBOARD & KPI
# ------------------------------------------
with tab2:
    df_stato = calcola_stato_magazzino()
    lotti_df = get_lotti_df()

    # Avviso Scadenze
    if not lotti_df.empty:
        lotti_df['data_scadenza'] = pd.to_datetime(lotti_df['data_scadenza'])
        oggi = pd.to_datetime(date.today())
        lotti_in_scadenza = lotti_df[(lotti_df['data_scadenza'] - oggi).dt.days <= 15]
        
        if not lotti_in_scadenza.empty:
            for _, row in lotti_in_scadenza.iterrows():
                giorni = (row['data_scadenza'] - oggi).days
                msg = f"In scadenza tra {giorni} giorni!" if giorni >= 0 else "SCADUTO!"
                st.error(f"🚨 **Lotto {row['codice_lotto']} ({row['prodotto']})**: {msg} (Data: {row['data_scadenza'].strftime('%Y-%m-%d')})")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valore Magazzino (Costo)", f"€ {df_stato['valore_totale_costo'].sum():,.2f}")
    col2.metric("Valore Magazzino (Mercato)", f"€ {df_stato['valore_totale_mercato'].sum():,.2f}")
    col3.metric("Incasso Totale Vendite", f"€ {df_stato['incasso_totale'].sum():,.2f}")
    col4.metric("Margine Netto Effettivo", f"€ {df_stato['margine_totale'].sum():,.2f}")

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Valore Stock per Prodotto (€)")
        chart_data_valore = df_stato.set_index('prodotto')[['valore_totale_costo', 'valore_totale_mercato']]
        chart_data_valore.columns = ['Costo Totale', 'Mercato Totale']
        st.bar_chart(chart_data_valore)

    with col_g2:
        st.subheader("Vendite e Margini (€)")
        chart_data_vendite = df_stato.set_index('prodotto')[['incasso_totale', 'margine_totale']]
        chart_data_vendite.columns = ['Incasso', 'Margine']
        st.bar_chart(chart_data_vendite)

# ------------------------------------------
# TAB 3: GESTIONE STOCK & MODIFICA VELOCE
# ------------------------------------------
with tab3:
    st.subheader("Stato del Magazzino per Prodotto")
    df_stato = calcola_stato_magazzino()
    
    st.dataframe(
        df_stato[[
            'prodotto', 'qta_disponibile', 'unita_misura',
            'costo_medio_ponderato', 'valore_mercato_unitario',
            'valore_totale_costo', 'valore_totale_mercato'
        ]].rename(columns={
            'prodotto': 'Prodotto',
            'qta_disponibile': 'Q.tà Presente',
            'unita_misura': 'U.M.',
            'costo_medio_ponderato': 'CMP (€)',
            'valore_mercato_unitario': 'Val. Mercato (€)',
            'valore_totale_costo': 'Tot. Costo (€)',
            'valore_totale_mercato': 'Tot. Mercato (€)'
        }),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    
    # MODIFICA VELOCE STOCK
    with st.expander("⚡ **Modifica Veloce Stock / Rettifica Rapida**", expanded=True):
        st.write("Modifica direttamente le quantità presenti in magazzino per ciascun lotto:")
        lotti_attivi = get_lotti_df()
        
        if not lotti_attivi.empty:
            lotto_sel_id = st.selectbox(
                "Seleziona Lotto da Rettificare", 
                options=lotti_attivi['id'].tolist(),
                format_func=lambda x: f"{lotti_attivi[lotti_attivi['id']==x]['prodotto'].values[0]} | Lotto: {lotti_attivi[lotti_attivi['id']==x]['codice_lotto'].values[0]} | Q.tà Attuale: {lotti_attivi[lotti_attivi['id']==x]['quantita_attuale'].values[0]}"
            )
            
            row_lotto = lotti_attivi[lotti_attivi['id'] == lotto_sel_id].iloc[0]
            
            with st.form("form_rettifica_rapida"):
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    nuova_qta = st.number_input("Nuova Quantità Rettificata", value=float(row_lotto['quantita_attuale']), min_value=0.0, step=1.0)
                with col_r2:
                    nuovo_costo_u = st.number_input("Nuovo Costo Unitario (€)", value=float(row_lotto['costo_acquisto_unitario']), min_value=0.01, step=0.1)
                
                if st.form_submit_button("⚡ Salva Modifica Rapida"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE lotti 
                        SET quantita_attuale = ?, costo_acquisto_unitario = ?
                        WHERE id = ?
                    """, (nuova_qta, nuovo_costo_u, lotto_sel_id))
                    conn.commit()
                    conn.close()
                    st.success("Giacenza del lotto aggiornata velocemente!")
                    st.rerun()
        else:
            st.info("Nessun lotto attivo presente da rettificare.")

    st.markdown("---")
    st.subheader("Dettaglio Lotti Attivi in Giacenza")
    lotti_df = get_lotti_df()
    
    if not lotti_df.empty:
        st.dataframe(
            lotti_df.rename(columns={
                'prodotto': 'Prodotto',
                'codice_lotto': 'Codice Lotto',
                'quantita_attuale': 'Q.tà Residua',
                'unita_misura': 'U.M.',
                'costo_acquisto_unitario': 'Costo Unit. (€)',
                'data_carico': 'Data Carico',
                'data_scadenza': 'Data Scadenza'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nessun lotto attivo disponibile al momento.")

# ------------------------------------------
# TAB 4: REPORT & STORICO
# ------------------------------------------
with tab4:
    st.subheader("Registro Storico Transazioni")
    
    movimenti_df = get_movimenti_df()
    
    if movimenti_df.empty:
        st.info("Nessuna transazione registrata nel database.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            prod_filtro = st.multiselect("Filtra per Prodotto", opzioni=movimenti_df['prodotto'].unique(), default=movimenti_df['prodotto'].unique())
        with col_f2:
            tipo_filtro = st.multiselect("Filtra per Tipo Operazione", opzioni=movimenti_df['tipo'].unique(), default=movimenti_df['tipo'].unique())
            
        df_filtrato = movimenti_df[
            (movimenti_df['prodotto'].isin(prod_filtro)) & 
            (movimenti_df['tipo'].isin(tipo_filtro))
        ]

        st.dataframe(
            df_filtrato.rename(columns={
                'data': 'Data/Ora',
                'prodotto': 'Prodotto',
                'tipo': 'Tipo',
                'quantita': 'Quantità',
                'unita_misura': 'U.M.',
                'prezzo_unitario': 'Prezzo Unit. (€)',
                'ricavo_totale': 'Ricavo (€)',
                'costo_totale': 'Costo (€)',
                'margine': 'Margine (€)',
                'note': 'Note'
            }),
            use_container_width=True,
            hide_index=True
        )

        csv_data = df_filtrato.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Storico in CSV",
            data=csv_data,
            file_name=f"storico_magazzino_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )