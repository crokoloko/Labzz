import random
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from database import (
    get_connection, get_prodotti_tutti_df, get_prodotti_disponibili_df, 
    set_sospetto, get_sospetto, aggiungi_cliente_se_nuovo
)

FASCE_ORARIE = [
    "🌅 1. Mattina al Campo (08:00 - 11:30)", 
    "☀️ 2. Sole alto al Fiume (11:30 - 15:00)", 
    "🌇 3. Pomeriggio tra i Sound System (15:00 - 18:30)", 
    "🌙 4. Calar del Sole al Mulino (18:30 - 22:00)", 
    "🌌 5. Notte Fonda / Soundclash (22:00 - 02:00)"
]

LISTA_NOMI_RAVER = [
    "Jan", "Klara", "Maxim", "Petra", "Tomas", "Lenka", "Wanja", 
    "Milan", "Zuzana", "Marek", "Sonja", "Ondra", "Katka", "Pavel", 
    "Hana", "Lukas", "Eliška", "Jakub", "Nikola", "David", "Veronika",
    "Martin", "Štěpán", "Markéta", "Filip", "Dominik", "Magda", "Sven",
    "Dmitri", "Natasha", "Alex", "Borislav", "Evelin", "Goran", "Ivana"
]

PUSHER_DISPONIBILI = [
    {"nome": "Vojta 'Il Veloce'", "quota_trattenuta": 0.25, "efficienza": 0.8},
    {"nome": "Kamil 'Ghost'", "quota_trattenuta": 0.35, "efficienza": 1.3},
    {"nome": "Anetka 'Bassi'", "quota_trattenuta": 0.40, "efficienza": 0.5}
]

GANGSTER_FORNITORI = [
    {"nome": "Zio Pavel (Furgone Grigio)", "frase": "«Robina fresca scesa dritta dai boschi di confine...»"},
    {"nome": "Katka 'Diesel'", "frase": "«O compri questo stock o stasera resti senza nafta per i generatori!»"},
    {"nome": "Marek 'Il Contrabbandiere'", "frase": "«Merce pulita, nascosta sotto i banchi di legno del vecchio mulino.»"},
    {"nome": "I Raminghi del Fiume", "frase": "«Senti come tremano i bassi? Questo stock spacca tutto il Sound System.»"},
    {"nome": "Bohumil 'Testadura'", "frase": "«Vedi di fare in fretta prima che la polizia forestale fiuti il fumo...»"}
]

def inizializza_pusher_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        for p in PUSHER_DISPONIBILI:
            cursor.execute("INSERT OR IGNORE INTO pusher (nome, quota_trattenuta, efficienza, assunto) VALUES (?, ?, ?, 0)", (p['nome'], p['quota_trattenuta'], p['efficienza']))
            cursor.execute("UPDATE pusher SET quota_trattenuta = ?, efficienza = ? WHERE nome = ?", (p['quota_trattenuta'], p['efficienza'], p['nome']))

def get_data_corrente_gioco():
    data_base = date(2026, 9, 27)
    giorni_trascorsi = st.session_state.get('giorni_trascorsi_offset', 0)
    return data_base + timedelta(days=giorni_trascorsi)

def e_festivo_o_weekend(data_rif):
    if data_rif.weekday() >= 5:
        return True, "Weekend / Raduno Massive nel Bosco 🎉"
    return False, "Giorni feriali / Autogestione al Mulino 🏕️"

def calcola_grado_reputazione(rep):
    if rep < 30:
        return "🌱 Nomade del Parcheggio"
    elif rep < 60:
        return "🥈 Raver Rispettato nel Bosco"
    elif rep < 85:
        return "🥇 Custode dei Sound System"
    else:
        return "👑 Re del Mulino di Skalákův"

def segna_debito_pagato(nome_cliente):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(ricavo_totale) FROM movimenti WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))
        tot_incassato = cursor.fetchone()[0] or 0.0
        cursor.execute("UPDATE movimenti SET pagamento = 'Subito' WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))
        st.session_state.soldi_cassa += tot_incassato

def genera_offerta_fornitore_casuale():
    if st.session_state.fornitori_visti_oggi >= st.session_state.max_fornitori_oggi:
        return

    st.session_state.fornitori_visti_oggi += 1
    gangster = random.choice(GANGSTER_FORNITORI)
    
    giorno_corrente = st.session_state.giorno
    moltiplicatore_giornaliero = 1.0 + min(2.5, (giorno_corrente - 1) * 0.18)
    
    rischio_sola = random.random() < (0.18 + min(0.30, giorno_corrente * 0.02))
    
    if rischio_sola:
        tipo_offerta = "⚠️ ATTENZIONE: Sospetta 'Sola' nel Bosco (Pacco)!"
        p_nome = "Skunk"
        qta = float(random.choice([80, 100, 150, 200]) * moltiplicatore_giornaliero)
        costo_u = round(random.uniform(3.00, 4.20), 2)
        valore_mercato_suggerito = 7.0
        gangster_frase_sola = f"«{gangster['nome']} ti guarda con un ghigno losco tra gli alberi...» " + gangster['frase']
    else:
        varieta_scelta = random.choices(
            ["Skunk", "Hash Dry", "Lemon Haze", "Frozen Hash"],
            weights=[40, 35, 18, 7],
            k=1
        )[0]
        
        if varieta_scelta == "Skunk":
            p_nome = "Skunk"
            qta = float(random.choice([60, 100, 150, 200]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(2.50, 3.50), 2)
            valore_mercato_suggerito = 7.0
            tipo_offerta = "🌿 Skunk del Campeggio"
        elif varieta_scelta == "Hash Dry":
            p_nome = "Hash Dry"
            qta = float(random.choice([40, 80, 120, 160]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(4.00, 5.50), 2)
            valore_mercato_suggerito = 10.0
            tipo_offerta = "🧱 Hash Dry Commerciale"
        elif varieta_scelta == "Lemon Haze":
            p_nome = "Lemon Haze"
            qta = float(random.choice([30, 60, 100, 130]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(6.50, 8.50), 2)
            valore_mercato_suggerito = 14.0
            tipo_offerta = "🍋 Lemon Haze (Selezionata al Mulino)"
        else:
            p_nome = "Frozen Hash"
            qta = float(random.choice([20, 35, 50, 70]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(10.00, 13.50), 2)
            valore_mercato_suggerito = 22.0
            tipo_offerta = "❄️ Frozen Hash (💎 Stock Leggendario del Bosco)"

        gangster_frase_sola = gangster['frase']

    qta = round(qta, 1)
    costo_tot = round(qta * costo_u, 2)

    st.session_state.offerta_fornitore = {
        "fornitore_nome": gangster["nome"],
        "fornitore_frase": gangster_frase_sola,
        "prodotto_nome": p_nome,
        "quantita": qta,
        "costo_unitario": costo_u,
        "costo_totale": costo_tot,
        "valore_mercato_suggerito": valore_mercato_suggerito,
        "tipo": tipo_offerta,
        "is_sola": rischio_sola,
        "codice_lotto": f"MULINO-{random.randint(100,999)}"
    }

def genera_cliente_in_negozio():
    prodotti_tutti = get_prodotti_tutti_df()
    if not prodotti_tutti.empty:
        prod = prodotti_tutti.sample(n=1).iloc[0]
        nome_c = random.choice(LISTA_NOMI_RAVER)
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
    sosp = get_sospetto()
    if sosp >= 75.0 or random.random() < 0.35:
        evento_tipo = random.choice(["polizia", "vip", "tossici", "festival"])
        
        if evento_tipo == "polizia":
            st.session_state.evento_attivo = {
                "tipo": "polizia",
                "titolo": "🚨 BLITZ POLIZIA FORESTALE / POSTO DI BLOCCO SUL FIUME!",
                "testo": f"Il livello di attenzione sul bosco è alto ({sosp:.1f}%). Le volanti controllano le strade sterrate d'accesso al mulino!"
            }
        elif evento_tipo == "vip":
            prodotti_disp = get_prodotti_disponibili_df()
            if not prodotti_disp.empty:
                prod_vip = prodotti_disp.sample(n=1).iloc[0]
                qta_vip = float(random.choice([5, 10, 15]))
                prezzo_vip = float(prod_vip['valore_mercato_unitario']) * 1.45
                st.session_state.evento_attivo = {
                    "tipo": "vip",
                    "titolo": "📱 RICHIESTA DAL PALCO PRINCIPALE",
                    "testo": f"Un sound system vicino ti manda un runner: «Ci servono urgentemente **{qta_vip}g di {prod_vip['nome']}** per i djs che suonano all'alba sul palco centrale. Ti pago **€{prezzo_vip:.2f}/g**!»",
                    "prodotto_id": int(prod_vip['id']),
                    "prodotto_nome": prod_vip['nome'],
                    "quantita": qta_vip,
                    "prezzo_offerto": prezzo_vip
                }
            else:
                st.session_state.evento_attivo = None
        elif evento_tipo == "festival":
            st.session_state.evento_attivo = {
                "tipo": "festival",
                "titolo": "🎉 PIENA PIENA AL RADUNO NEL BOSCO!",
                "testo": "Centinaia di furgoni e carovane sono arrivate da tutta Europa per il free party! La richiesta di mercato schizza alle stelle (+20% sui prezzi di vendita per oggi)."
            }
        else:
            st.session_state.evento_attivo = {
                "tipo": "tossici",
                "titolo": "🧟 RIVALI DEL CAMPEGGIO INCAZZATI!",
                "testo": "Dei tipacci ubriachi del parcheggio creano scompiglio vicino ai generatori cercando di seminare guai!"
            }
    else:
        st.session_state.evento_attivo = None

def esegui_transazione_vendita(cli_att, prezzo_per_g, tipo_pagamento, callback_log=None):
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
                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezz_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note)
                VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cli_att['prodotto_id'], l_id, prelievo, prezzo_per_g, ricavo_q, costo_q, margine_q, cli_att['nome'], tipo_pagamento, f"Spaccio al Campeggio - Lotto {lotto['codice_lotto']}")) if "prezz_unitario" in [c[1] for c in cursor.execute("PRAGMA table_info(movimenti)").fetchall()] else cursor.execute("""
                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note)
                VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cli_att['prodotto_id'], l_id, prelievo, prezzo_per_g, ricavo_q, costo_q, margine_q, cli_att['nome'], tipo_pagamento, f"Spaccio al Campeggio - Lotto {lotto['codice_lotto']}"))

    if tipo_pagamento == "Subito":
        st.session_state.soldi_cassa += totale_incasso

    st.session_state.energia = max(0, st.session_state.energia - 10)
    st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 3)
    st.session_state.reputazione = min(100, st.session_state.reputazione + 1)
    
    incremento_sospetto = cli_att['quantita_richiesta'] * 0.15
    if "Frozen" in cli_att['prodotto_nome']:
        incremento_sospetto *= 1.8
    set_sospetto(get_sospetto() + incremento_sospetto)

    if callback_log:
        callback_log(f"✅ SPACCIO: {cli_att['nome']} ha preso {cli_att['quantita_richiesta']}g di '{cli_att['prodotto_nome']}' al campeggio (+€{totale_incasso:.2f})")
