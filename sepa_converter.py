import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime

def generate_sepa_xml(df: pd.DataFrame,
                      debtor_name: str,
                      debtor_iban: str,
                      currency: str,
                      debtor_bic: str) -> str:
    """
    Build a pain.001.001.09 SEPA XML file with both unstructured (Ustrd)
    and structured (Strd/CdtrRefInf) references.
    Columns are picked by your provided indices:
      • Creditor Name → df.columns[4]
      • IBAN            → df.columns[3]
      • Amount          → df.columns[14]
      • Reference/Desc  → df.columns[37]
    """
    # --- 1) Map by fixed column positions ---
    benef_col = df.columns[4]
    iban_col  = df.columns[3]
    amount_col= df.columns[14]
    ref_col   = df.columns[37]

    # Drop rows missing essential data
    df = df.dropna(subset=[iban_col, amount_col])

    # Normalize amount to float
    df["Amount_Clean"] = (
        df[amount_col].astype(str)
                       .str.replace(",", ".")
                       .str.replace(" ", "")
                       .astype(float)
    )

    # SEPA header values
    ctrl_sum = df["Amount_Clean"].sum()
    now_iso  = datetime.now().isoformat()
    msg_id   = f"MSG{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # XML namespace
    NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
    root = ET.Element("Document", xmlns=NS)
    cstmr = ET.SubElement(root, "CstmrCdtTrfInitn")

    # Group Header
    grp = ET.SubElement(cstmr, "GrpHdr")
    ET.SubElement(grp, "MsgId")   .text = msg_id
    ET.SubElement(grp, "CreDtTm") .text = now_iso
    ET.SubElement(grp, "NbOfTxs").text = str(len(df))
    ET.SubElement(grp, "CtrlSum").text = f"{ctrl_sum:.2f}"
    initg = ET.SubElement(grp, "InitgPty")
    ET.SubElement(initg, "Nm")    .text = debtor_name

    # Payment Information
    pmt = ET.SubElement(cstmr, "PmtInf")
    ET.SubElement(pmt, "PmtInfId") .text = f"PmtInf{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(pmt, "PmtMtd")   .text = "TRF"
    ET.SubElement(pmt, "BtchBookg").text = "true"
    ET.SubElement(pmt, "NbOfTxs")  .text = str(len(df))
    ET.SubElement(pmt, "CtrlSum")  .text = f"{ctrl_sum:.2f}"
    pti = ET.SubElement(pmt, "PmtTpInf")
    svc = ET.SubElement(pti, "SvcLvl")
    ET.SubElement(svc, "Cd")       .text = "SEPA"
    ET.SubElement(pmt, "ReqdExctnDt").text = datetime.now().strftime("%Y-%m-%d")
    dbtr = ET.SubElement(pmt, "Dbtr")
    ET.SubElement(dbtr, "Nm")      .text = debtor_name
    dbac = ET.SubElement(pmt, "DbtrAcct")
    dbid = ET.SubElement(dbac, "Id")
    ET.SubElement(dbid, "IBAN")    .text = debtor_iban
    dagt = ET.SubElement(pmt, "DbtrAgt")
    fin  = ET.SubElement(dagt, "FinInstnId")
    ET.SubElement(fin, "BIC")      .text = debtor_bic
    ET.SubElement(pmt, "ChrgBr")   .text = "SLEV"

    # Build each transaction
    for idx, row in df.iterrows():
        cdt = ET.SubElement(pmt, "CdtTrfTxInf")

        # Payment ID (use your Reference column)
        pid = ET.SubElement(cdt, "PmtId")
        raw_ref = str(row[ref_col]).strip()
        reference = raw_ref[:35] if raw_ref else f"TRX-{idx+1:05d}"
        ET.SubElement(pid, "EndToEndId").text = reference

        # Amount element
        amt  = ET.SubElement(cdt, "Amt")
        inst = ET.SubElement(amt, "InstdAmt", Ccy=currency)
        inst.text = f"{row['Amount_Clean']:.2f}"

        # Creditor details
        cdr = ET.SubElement(cdt, "Cdtr")
        ET.SubElement(cdr, "Nm").text   = str(row[benef_col])[:70]
        cac = ET.SubElement(cdt, "CdtrAcct")
        cid = ET.SubElement(cac, "Id")
        ET.SubElement(cid, "IBAN").text = row[iban_col]

        # Remittance: unstructured + structured
        rmt = ET.SubElement(cdt, "RmtInf")
        ET.SubElement(rmt, "Ustrd").text = reference

        strd = ET.SubElement(rmt, "Strd")
        cri  = ET.SubElement(strd, "CdtrRefInf")
        tp   = ET.SubElement(cri, "Tp")
        cop  = ET.SubElement(tp, "CdOrPrtry")
        ET.SubElement(cop, "Cd")        .text = "SCOR"
        ET.SubElement(cri, "Ref")       .text = reference

    # Write XML to disk
    out_file = f"sepa_{msg_id}.xml"
    ET.ElementTree(root).write(out_file, encoding="utf-8", xml_declaration=True)
    return out_file

def main():
    st.title("SEPA XML Generator for LHV Bank")
    st.sidebar.header("Debtor Information")
    debtor_name = st.sidebar.text_input("Debtor Name")
    debtor_iban = st.sidebar.text_input("Debtor IBAN")
    debtor_bic  = st.sidebar.text_input("Debtor BIC")
    currency    = st.sidebar.text_input("Currency", "EUR")

    st.header("Upload Payouts CSV")
    uploaded = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        st.write("Using columns by position:")
        st.text(f"  Creditor Name  = df.columns[4]  → {df.columns[4]}")
        st.text(f"  IBAN            = df.columns[3]  → {df.columns[3]}")
        st.text(f"  Amount          = df.columns[14] → {df.columns[14]}")
        st.text(f"  Reference       = df.columns[37] → {df.columns[37]}")

        if st.button("Generate SEPA XML"):
            if not all([debtor_name, debtor_iban, debtor_bic]):
                st.error("Please fill in all debtor fields.")
            else:
                xml_file = generate_sepa_xml(df, debtor_name, debtor_iban, currency, debtor_bic)
                st.success(f"Generated `{xml_file}`")
                with open(xml_file, "rb") as f:
                    st.download_button("Download XML", f, file_name=xml_file, mime="application/xml")

if __name__ == "__main__":
    main()
