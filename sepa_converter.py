import streamlit as st
import csv
import io
import xml.etree.ElementTree as ET
from decimal import Decimal

# Namespaces
NS = 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
SCHEMA_LOCATION = f"{NS} pain.001.001.09.xsd"
ET.register_namespace('', NS)
ET.register_namespace('xsi', XSI)


def convert_csv_to_xml(csv_bytes):
    data = csv_bytes.decode('utf-8')
    reader = csv.reader(io.StringIO(data))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if len(rows) < 2:
        return None
    header, payments = rows[0], rows[1:]

    # Header fields
    msgid = header[2].strip() or 'MSG1'
    creation_date = header[32].split()[-1]
    debtor_name = header[4].strip()
    debtor_iban = header[3].replace(' ', '')
    debtor_bic = header[10].strip()

    # Totals
    amounts = [Decimal(r[13].replace(',', '.')) for r in payments]
    ctrl_sum = sum(amounts)
    nb_tx = len(payments)

    # Root Document
    doc = ET.Element(f'{{{NS}}}Document', {
        'xmlns': NS,
        'xmlns:xsi': XSI,
        'xsi:schemaLocation': SCHEMA_LOCATION
    })
    cstmr = ET.SubElement(doc, f'{{{NS}}}CstmrCdtTrfInitn')

    # Group Header
    grp = ET.SubElement(cstmr, f'{{{NS}}}GrpHdr')
    ET.SubElement(grp, f'{{{NS}}}MsgId').text = msgid
    ET.SubElement(grp, f'{{{NS}}}CreDtTm').text = f"{creation_date}T00:00:00"
    ET.SubElement(grp, f'{{{NS}}}NbOfTxs').text = str(nb_tx)
    ET.SubElement(grp, f'{{{NS}}}CtrlSum').text = f"{ctrl_sum:.2f}"
    initpty = ET.SubElement(grp, f'{{{NS}}}InitgPty')
    ET.SubElement(initpty, f'{{{NS}}}Nm').text = debtor_name

    # Payment Information
    pinf = ET.SubElement(cstmr, f'{{{NS}}}PmtInf')
    ET.SubElement(pinf, f'{{{NS}}}PmtInfId').text = msgid
    ET.SubElement(pinf, f'{{{NS}}}PmtMtd').text = 'TRF'
    ET.SubElement(pinf, f'{{{NS}}}BtchBookg').text = 'false'
    ET.SubElement(pinf, f'{{{NS}}}NbOfTxs').text = str(nb_tx)
    ET.SubElement(pinf, f'{{{NS}}}CtrlSum').text = f"{ctrl_sum:.2f}"
    ptype = ET.SubElement(pinf, f'{{{NS}}}PmtTpInf')
    svc = ET.SubElement(ptype, f'{{{NS}}}SvcLvl')
    ET.SubElement(svc, f'{{{NS}}}Cd').text = 'SEPA'
    reqd = ET.SubElement(pinf, f'{{{NS}}}ReqdExctnDt')
    ET.SubElement(reqd, f'{{{NS}}}Dt').text = creation_date

    # Debtor
    dbtr = ET.SubElement(pinf, f'{{{NS}}}Dbtr')
    ET.SubElement(dbtr, f'{{{NS}}}Nm').text = debtor_name
    dbacct = ET.SubElement(pinf, f'{{{NS}}}DbtrAcct')
    dbid = ET.SubElement(dbacct, f'{{{NS}}}Id')
    ET.SubElement(dbid, f'{{{NS}}}IBAN').text = debtor_iban
    dbagt = ET.SubElement(pinf, f'{{{NS}}}DbtrAgt')
    finid = ET.SubElement(dbagt, f'{{{NS}}}FinInstnId')
    ET.SubElement(finid, f'{{{NS}}}BICFI').text = debtor_bic
    ET.SubElement(pinf, f'{{{NS}}}ChrgBr').text = 'SLEV'

    # Transactions
    for r in payments:
        tx = ET.SubElement(pinf, f'{{{NS}}}CdtTrfTxInf')
        # Payment ID
        pid = ET.SubElement(tx, f'{{{NS}}}PmtId')
        e2e = r[34].strip() if len(r) > 34 and r[34].strip() else r[2].strip()
        ET.SubElement(pid, f'{{{NS}}}EndToEndId').text = e2e

        # Amount
        amt = ET.SubElement(tx, f'{{{NS}}}Amt')
        inst = ET.SubElement(amt, f'{{{NS}}}InstdAmt', Ccy=r[12])
        inst.text = r[13].replace(',', '.')

        # Creditor Agent
        cagt = ET.SubElement(tx, f'{{{NS}}}CdtrAgt')
        fin = ET.SubElement(cagt, f'{{{NS}}}FinInstnId')
        ET.SubElement(fin, f'{{{NS}}}BICFI').text = r[10].strip()

        # Creditor
        cdt = ET.SubElement(tx, f'{{{NS}}}Cdtr')
        ET.SubElement(cdt, f'{{{NS}}}Nm').text = r[4].strip()
        pstl = ET.SubElement(cdt, f'{{{NS}}}PstlAdr')
        addr1, addr2 = r[5].strip(), r[6].strip()
        combined = f"{addr1}, {addr2}" if addr1 and addr2 else addr1 or addr2
        if combined:
            ET.SubElement(pstl, f'{{{NS}}}AdrLine').text = combined

        # Creditor Account
        cact = ET.SubElement(tx, f'{{{NS}}}CdtrAcct')
        acid = ET.SubElement(cact, f'{{{NS}}}Id')
        ET.SubElement(acid, f'{{{NS}}}IBAN').text = r[35].replace(' ', '')

        # Remittance Information
        rmt = ET.SubElement(tx, f'{{{NS}}}RmtInf')
        ET.SubElement(rmt, f'{{{NS}}}Ustrd').text = r[2].strip()
        ref_val = r[36].strip() if len(r) > 36 and r[36].strip() else 'Ryft'
        strd = ET.SubElement(rmt, f'{{{NS}}}Strd')
        cri = ET.SubElement(strd, f'{{{NS}}}CdtrRefInf')
        tp = ET.SubElement(cri, f'{{{NS}}}Tp')
        cdorp = ET.SubElement(tp, f'{{{NS}}}CdOrPrtry')
        ET.SubElement(cdorp, f'{{{NS}}}Cd').text = 'SCOR'
        ET.SubElement(cri, f'{{{NS}}}Ref').text = ref_val

    # Serialize
    buf = io.BytesIO()
    ET.ElementTree(doc).write(buf, xml_declaration=True, encoding='utf-8', method='xml')
    return buf.getvalue()

# Streamlit UI
st.title('CSV to pain.001.001.09 Converter')
uploaded = st.file_uploader('Upload your CSV file', type='csv')
if uploaded:
    xml_bytes = convert_csv_to_xml(uploaded.getvalue())
    if xml_bytes:
        st.download_button('Download XML', data=xml_bytes, file_name='payments.xml', mime='application/xml')
    else:
        st.error('Failed to parse CSV. Ensure expected format.')
