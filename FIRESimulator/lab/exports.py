"""Premium CSV and PDF exports of a lab scenario, built from the same results the page shows."""
import csv
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from FIRE import pdf_report as pr

FREQ = {'weekly': 'Weekly', 'biweekly': 'Bi-weekly', 'bimonthly': 'Twice a month', 'monthly': 'Monthly',
        'quarterly': 'Quarterly', 'biannual': 'Twice a year', 'yearly': 'Yearly'}
ACCT = {'cash': 'Cash / savings', 'employer': 'Employer retirement', 'ira': 'IRA', 'hsa': 'HSA',
        'taxable': 'Taxable investment', 'education': 'Education (529)', 'alt': 'Alternative'}
KIND = {'income': 'Income', 'expense': 'Expense', 'account': 'Account'}


def _when(item, plan_age):
    if item['kind'] == 'account':
        return '', ''
    start = 'FI' if item.get('start_at_fi') else (item.get('start_age') if item.get('start_age') is not None else 'Now')
    end = {'fi': 'FI', 'age': item.get('end_age'), 'life': f'Age {plan_age}'}.get(item.get('end_mode'), '')
    return start, end


def _item_row(item, plan_age):
    start, end = _when(item, plan_age)
    acct = item['kind'] == 'account'
    return [KIND[item['kind']], item['name'], item['amount'],
            ACCT.get(item.get('account_type'), '') if acct else FREQ.get(item['frequency'], ''),
            '' if acct else item.get('growth_pct', ''), start, end,
            (item.get('contribution_type') or '') if acct else '']


ITEM_HEADER = ['Type', 'Name', 'Amount / balance', 'Frequency / account type', 'Annual change %', 'Starts', 'Ends',
               'Contribution type']


def _years(results):
    return list(zip(results['ages'], results['income'], results['expenses'], results['taxes'], results['saved'],
                    results['withdrawn'], results['p10'], results['p50'], results['p90'], results['magic']))


def write_csv(response, sc, items, results):
    w = csv.writer(response)
    w.writerow([sc.name])
    w.writerow(['Current age', sc.age, 'Plan to age', sc.plan_to_age, 'Filing status', sc.get_filing_status_display(),
                'State', sc.state])
    w.writerow(['FI age', results['fi_age'] if results['fi_age'] is not None else 'Never',
                '4% rule age', results['rule_age'] or '', 'Chance plan holds', results['success_pct'] or ''])
    w.writerow([])
    w.writerow(['Age', 'Income', 'Spending', 'Taxes', 'Saved', 'Withdrawn', 'Net worth (10th pct)',
                'Net worth (median)', 'Net worth (90th pct)', 'Magic number (4% rule)'])
    for row in _years(results):
        w.writerow(row)
    w.writerow([])
    w.writerow(ITEM_HEADER)
    for item in items:
        w.writerow(_item_row(item, sc.plan_to_age))


def build_pdf(sc, items, results):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            title=f'{sc.name} - FI Planner', author='FI Planner')
    styles = getSampleStyleSheet()
    title = ParagraphStyle('t', parent=styles['Title'], alignment=0, textColor=pr.GREEN, fontSize=22, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], textColor=pr.GREEN, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle('b', parent=styles['BodyText'], fontSize=10, leading=14)
    small = ParagraphStyle('s', parent=body, fontSize=8, textColor=colors.grey)
    label = ParagraphStyle('l', parent=small, textColor=colors.HexColor('#555555'))
    value = ParagraphStyle('v', parent=body, fontSize=15, leading=18, textColor=pr.GREEN, fontName='Helvetica-Bold')
    cell = ParagraphStyle('c', parent=body, fontSize=8, leading=10)

    fi, plan = results['fi_age'], sc.plan_to_age
    story = [Paragraph(escape(sc.name), title),
             Paragraph(f'Financial independence scenario &middot; age {sc.age}, planning to age {plan} &middot; '
                       f'{sc.get_filing_status_display()}', small), Spacer(1, 10)]

    if results['status'] != 'ok':
        story.append(Paragraph('This scenario has no incomes, expenses or accounts yet.', body))
    else:
        verdict = (f'Financial independence at age {fi}.' if fi is not None
                   else 'On the current inputs you do not reach financial independence before your plan age.')
        table = Table([[Paragraph(f'<b>{verdict}</b>', body)]], colWidths=[pr.WIDTH])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E6F2EC') if fi is not None else colors.HexColor('#FCEBE2')),
            ('LINEBEFORE', (0, 0), (0, -1), 4, pr.GREEN if fi is not None else pr.ORANGE),
            ('LEFTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
        story += [table, Spacer(1, 10)]

        success = results['success_pct']
        kpis = [('Current net worth', pr._money(results['net_worth_now'])), ('FI age', fi if fi is not None else 'Never'),
                ('4% rule age', results['rule_age'] or '\u2014'),
                (f'Chance plan holds to {plan}', f'{success}%' if success is not None else 'N/A'),
                ('4% rule number at FI age', pr._money(results['fi_number']) if results['fi_number'] else '\u2014'),
                ('Yearly surplus now', pr._money(results.get('surplus_now', 0))),
                ('Unallocated cash', pr._money(results['unallocated_now'])), ('Years planned', plan - sc.age)]
        rows = [[], []]
        for i, (name, val) in enumerate(kpis):
            rows[i // 4].append([Paragraph(str(name), label), Paragraph(str(val), value)])
        kpi_table = Table(rows, colWidths=[pr.WIDTH / 4] * 4)
        kpi_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, pr.MUTED), ('INNERGRID', (0, 0), (-1, -1), 0.5, pr.MUTED),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
        story += [kpi_table, Spacer(1, 12)]

        chart = {'ages': results['ages'], 'net_worths': results['p50'], 'magic_numbers': results['magic'],
                 'income': results['income'], 'expenses': results['expenses'], 'savings': results['saved']}
        story += [pr._net_worth_chart(chart),
                  Paragraph('Net worth is the median of 1,000 Monte Carlo simulations. Projections are estimates '
                            'and not financial advice.', small),
                  Spacer(1, 6), KeepTogether([Paragraph('Cash flow', h2), pr._cash_flow_chart(chart)])]

        if results.get('retire_options'):
            opts = results['retire_options']
            head = ['Retire at age'] + [str(o['age']) for o in opts]
            odds = ['Chance money lasts'] + [f"{o['success']}%" for o in opts]
            ot = Table([head, odds], colWidths=[pr.WIDTH * 0.2] + [pr.WIDTH * 0.8 / len(opts)] * len(opts))
            ot.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 8), ('GRID', (0, 0), (-1, -1), 0.25, pr.MUTED),
                                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4F6F4')),
                                    ('ALIGN', (1, 0), (-1, -1), 'CENTER')]))
            story += [KeepTogether([Paragraph('What if you retire at a different age?', h2), ot])]

    if items:
        rows = [ITEM_HEADER] + [[Paragraph(escape(str(c)), cell) for c in _item_row(i, plan)] for i in items]
        rows[1:] = [[Paragraph(escape(pr._money(c) if n == 2 else str(c)), cell)
                     for n, c in enumerate(_item_row(i, plan))] for i in items]
        rows[0] = [Paragraph(f'<b>{h}</b>', cell) for h in ITEM_HEADER]
        it = Table(rows, repeatRows=1, colWidths=[pr.WIDTH * w for w in (.09, .2, .13, .2, .1, .08, .08, .12)])
        it.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.25, pr.MUTED),
                                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6F2EC')),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [Paragraph('Your inputs', h2), it]

    if results['status'] == 'ok':
        header = ['Age', 'Income', 'Spending', 'Taxes', 'Saved', 'Withdrawn', 'Net worth', 'Magic number (4%)']
        data = [header] + [[age, pr._money(inc), pr._money(exp), pr._money(tax), pr._money(sv), pr._money(wd),
                            pr._money(p50), pr._money(mg)]
                           for age, inc, exp, tax, sv, wd, _p10, p50, _p90, mg in _years(results)]
        yt = Table(data, repeatRows=1, colWidths=[pr.WIDTH * 0.08] + [pr.WIDTH * 0.132] * 7)
        yt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), pr.GREEN), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F6F4')]),
            ('GRID', (0, 0), (-1, -1), 0.25, pr.MUTED)]))
        story += [Paragraph('Year by year', h2), yt]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.75 * inch, 0.4 * inch, 'FI Planner - fiplanner.app')
        canvas.drawRightString(letter[0] - 0.75 * inch, 0.4 * inch, f'Page {document.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
