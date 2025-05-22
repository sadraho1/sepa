import streamlit as st
import csv
import io
import xml.etree.ElementTree as ET
from decimal import Decimal

# ISO20022 namespaces and schema locations
NS = 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09'
EXT_NS = 'urn:iso:std:iso:20022:tech:xsd:supl.001.001.01'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
SCHEMA_LOCATION = f"{NS} pain.001.001.09.xsd {EXT_NS} supl.001.001.01.xsd"


def convert_csv_to_xml(csv_bytes):
    # Parse CSV
    decoded = csv_bytes.decode('utf-8')
    reader = csv.reader(io.StringIO(decoded))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
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

    # Root element as CstmrCdtTrfInitn with default ns and schema attributes
    root = ET.Element(
        f'{{{NS}}}CstmrCdtTrfInitn',
        {
            'xmlns': NS,
            'xmlns:ext': EXT_NS,
            'xmlns:xsi': XSI_NS,
            'xsi:schemaLocation': SCHEMA_LOCATION
        }
    )

    # Group Header
    grp = ET.SubElement(root, 'GrpHdr')
    ET.SubElement(grp, 'MsgId').text = msgid
    ET.SubElement(grp, 'CreDtTm').text = f"{creation_date}T00:00:00"
    ET.SubElement(grp, 'NbOfTxs').text = str(nb_tx)
    ET.SubElement(grp, 'CtrlSum').text = f"{ctrl_sum:.2f}"
    initpty = ET.SubElement(grp, 'InitgPty')
    ET.SubElement(initpty, 'Nm').text = debtor_name

    # Payment Information
    pinf = ET.SubElement(root, 'PmtInf')
    ET.SubElement(pinf, 'PmtInfId').text = msgid
    ET.SubElement(pinf, 'PmtMtd').text = 'TRF'
    ET.SubElement(pinf, 'BtchBookg').text = 'false'
    ET.SubElement(pinf, 'NbOfTxs').text = str(nb_tx)
    ET.SubElement(pinf, 'CtrlSum').text = f"{ctrl_sum:.2f}"
    ptype = ET.SubElement(pinf, 'PmtTpInf')
    svc = ET.SubElement(ptype, 'SvcLvl')
    ET.SubElement(svc, 'Cd').text = 'SEPA'
    reqd = ET.SubElement(pinf, 'ReqdExctnDt')
    ET.SubElement(reqd, 'Dt').text = creation_date

    # Debtor
    dbtr = ET.SubElement(pinf, 'Dbtr')
    ET.SubElement(dbtr, 'Nm').text = debtor_name
    dbacct = ET.SubElement(pinf, 'DbtrAcct')
    dbid = ET.SubElement(dbacct, 'Id')
    ET.SubElement(dbid, 'IBAN').text = debtor_iban
    dbagt = ET.SubElement(pinf, 'DbtrAgt')
    finid = ET.SubElement(dbagt, 'FinInstnId')
    ET.SubElement(finid, 'BICFI').text = debtor_bic
    ET.SubElement(pinf, 'ChrgBr').text = 'SLEV'

    # Transactions
    for r in payments:
        tx = ET.SubElement(pinf, 'CdtTrfTxInf')
        # PmtId
        pid = ET.SubElement(tx, 'PmtId')
        e2e = r[34].strip() if len(r) > 34 and r[34].strip() else r[2].strip()
        ET.SubElement(pid, 'EndToEndId').text = e2e
        # Amount
        amt = ET.SubElement(tx, 'Amt')
        inst = ET.SubElement(amt, 'InstdAmt', Ccy=r[12])
        inst.text = r[13].replace(',', '.')
        # Creditor Agent
        cagt = ET.SubElement(tx, 'CdtrAgt')
        fin = ET.SubElement(cagt, 'FinInstnId')
        ET.SubElement(fin, 'BICFI').text = r[10].strip()
        # Creditor
        cdt = ET.SubElement(tx, 'Cdtr')
        ET.SubElement(cdt, 'Nm').text = r[4].strip()
        pstl = ET.SubElement(cdt, 'PstlAdr')
        addr1, addr2 = r[5].strip(), r[6].strip()
        combined = f"{addr1}, {addr2}" if addr1 and addr2 else addr1 or addr2
        if combined:
            ET.SubElement(pstl, 'AdrLine').text = combined
        # Creditor Account
        cact = ET.SubElement(tx, 'CdtrAcct')
        acid = ET.SubElement(cact, 'Id')
        ET.SubElement(acid, 'IBAN').text = r[35].replace(' ', '')
        # Remittance
        rmt = ET.SubElement(tx, 'RmtInf')
        ET.SubElement(rmt, 'Ustrd').text = r[2].strip()
        ref_val = r[36].strip() if len(r) > 36 and r[36].strip() else 'Ryft'
        strd = ET.SubElement(rmt, 'Strd')
        cri = ET.SubElement(strd, 'CdtrRefInf')
        tp = ET.SubElement(cri, 'Tp')
        cdorp = ET.SubElement(tp, 'CdOrPrtry')
        ET.SubElement(cdorp, 'Cd').text = 'SCOR'
        ET.SubElement(cri, 'Ref').text = ref_val

    # Serialize to bytes
    buffer = io.BytesIO()
    ET.ElementTree(root).write(buffer, xml_declaration=True, encoding='utf-8', method='xml')
    return buffer.getvalue()

# Streamlit UI
st.title('CSV to pain.001.001.09 Converter')

uploaded = st.file_uploader('Upload your CSV file', type='csv')
if uploaded:
    xml_bytes = convert_csv_to_xml(uploaded.getvalue())
    if xml_bytes:
        st.download_button('Download XML', data=xml_bytes, file_name='payments.xml', mime='application/xml')
    else:
        st.error('Failed to parse CSV. Ensure it matches the expected format.')import streamlit as st
import csv
import io
import xml.etree.ElementTree as ET
from decimal import Decimal

# ISO20022 namespace
NS = 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09'
ET.register_namespace('', NS)


def convert_csv_to_xml(csv_bytes):
    # Read CSV content
    decoded = csv_bytes.decode('utf-8')
    reader = csv.reader(io.StringIO(decoded))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return None
    header = rows[0]
    payments = rows[1:]

    # Header info
    msgid = header[2] or 'MSG1'
    creation_date = header[32].split()[-1]
    debtor_name = header[4]
    debtor_iban = header[3].replace(' ', '')
    debtor_bic = header[10]

    # Sum and count
    amounts = [Decimal(r[13].replace(',', '.')) for r in payments]
    ctrlsum = sum(amounts)
    nb_tx = len(payments)

    # Build XML
    doc = ET.Element(f'{{{NS}}}Document')
    initn = ET.SubElement(doc, 'CstmrCdtTrfInitn')

    # Group Header
    grp = ET.SubElement(initn, 'GrpHdr')
    ET.SubElement(grp, 'MsgId').text = msgid
    ET.SubElement(grp, 'CreDtTm').text = f"{creation_date}T00:00:00"
    ET.SubElement(grp, 'NbOfTxs').text = str(nb_tx)
    ET.SubElement(grp, 'CtrlSum').text = f"{ctrlsum:.2f}"
    initpty = ET.SubElement(grp, 'InitgPty')
    ET.SubElement(initpty, 'Nm').text = debtor_name

    # Payment Info
    pinf = ET.SubElement(initn, 'PmtInf')
    ET.SubElement(pinf, 'PmtInfId').text = msgid
    ET.SubElement(pinf, 'PmtMtd').text = 'TRF'
    ET.SubElement(pinf, 'BtchBookg').text = 'false'
    ET.SubElement(pinf, 'NbOfTxs').text = str(nb_tx)
    ET.SubElement(pinf, 'CtrlSum').text = f"{ctrlsum:.2f}"
    ptype = ET.SubElement(pinf, 'PmtTpInf')
    svclvl = ET.SubElement(ptype, 'SvcLvl')
    ET.SubElement(svclvl, 'Cd').text = 'SEPA'
    reqd = ET.SubElement(pinf, 'ReqdExctnDt')
    ET.SubElement(reqd, 'Dt').text = creation_date

    # Debtor
    dbtr = ET.SubElement(pinf, 'Dbtr')
    ET.SubElement(dbtr, 'Nm').text = debtor_name
    dbtr_acct = ET.SubElement(pinf, 'DbtrAcct')
    dbtr_id = ET.SubElement(dbtr_acct, 'Id')
    ET.SubElement(dbtr_id, 'IBAN').text = debtor_iban
    dbagt = ET.SubElement(pinf, 'DbtrAgt')
    dbagt_id = ET.SubElement(dbagt, 'FinInstnId')
    ET.SubElement(dbagt_id, 'BICFI').text = debtor_bic
    ET.SubElement(pinf, 'ChrgBr').text = 'SLEV'

    # Transactions
    for r in payments:
        tx = ET.SubElement(pinf, 'CdtTrfTxInf')
        # EndToEndId
        pid = ET.SubElement(tx, 'PmtId')
        e2e = r[34].strip() if len(r) > 34 and r[34].strip() else r[2].strip()
        ET.SubElement(pid, 'EndToEndId').text = e2e
        # Amount
        amt = ET.SubElement(tx, 'Amt')
        inst_amt = ET.SubElement(amt, 'InstdAmt', Ccy=r[12])
        inst_amt.text = r[13].replace(',', '.')
        # Creditor Agent
        cagt = ET.SubElement(tx, 'CdtrAgt')
        fin = ET.SubElement(cagt, 'FinInstnId')
        ET.SubElement(fin, 'BICFI').text = r[10]
        # Creditor
        cdt = ET.SubElement(tx, 'Cdtr')
        ET.SubElement(cdt, 'Nm').text = r[4]
        pstl = ET.SubElement(cdt, 'PstlAdr')
        addr1, addr2 = r[5].strip(), r[6].strip()
        combined = f"{addr1}, {addr2}" if addr1 and addr2 else addr1 or addr2
        if combined:
            ET.SubElement(pstl, 'AdrLine').text = combined
        # Creditor Account
        cact = ET.SubElement(tx, 'CdtrAcct')
        cact_id = ET.SubElement(cact, 'Id')
        ET.SubElement(cact_id, 'IBAN').text = r[35].replace(' ', '')
        # Remittance
        rmt = ET.SubElement(tx, 'RmtInf')
        ET.SubElement(rmt, 'Ustrd').text = r[2].strip()
        ref_val = r[36].strip() if len(r) > 36 and r[36].strip() else 'Ryft'
        strd = ET.SubElement(rmt, 'Strd')
        cri = ET.SubElement(strd, 'CdtrRefInf')
        tp = ET.SubElement(cri, 'Tp')
        cdorp = ET.SubElement(tp, 'CdOrPrtry')
        ET.SubElement(cdorp, 'Cd').text = 'SCOR'
        ET.SubElement(cri, 'Ref').text = ref_val

    # Serialize XML
    buffer = io.BytesIO()
    ET.ElementTree(doc).write(buffer, xml_declaration=True, encoding='utf-8', method='xml')
    return buffer.getvalue()

# Streamlit UI
st.title('CSV to pain.001.001.09 Converter')

uploaded = st.file_uploader('Upload your CSV file', type='csv')
if uploaded is not None:
    xml_bytes = convert_csv_to_xml(uploaded.getvalue())
    if xml_bytes:
        st.download_button(
            label='Download XML',
            data=xml_bytes,
            file_name='payments.xml',
            mime='application/xml'
        )
    else:
        st.error('Failed to parse CSV. Ensure it matches the expected format.')
