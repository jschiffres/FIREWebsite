"""Premium PDF export of the plan dashboard, drawn server-side with ReportLab."""
from io import BytesIO

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

GREEN = colors.HexColor('#285C53')
ORANGE = colors.HexColor('#EC652B')
PURPLE = colors.HexColor('#4F378A')
MUTED = colors.HexColor('#D8DDD8')
INK = colors.HexColor('#1d1919')
WIDTH = letter[0] - 1.5 * inch


def _money(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    return ('-' if value < 0 else '') + '${:,.0f}'.format(abs(value))


def _short(value):
    value = float(value)
    for limit, suffix in ((1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
        if abs(value) >= limit:
            return '${:.1f}{}'.format(value / limit, suffix)
    return '${:.0f}'.format(value)


def _legend(drawing, items, x, y):
    legend = Legend()
    legend.x, legend.y = x, y
    legend.alignment = 'right'
    legend.fontSize = 8
    legend.columnMaximum = 1
    legend.deltax = 70
    legend.colorNamePairs = items
    drawing.add(legend)


def _net_worth_chart(data):
    ages = data['ages']
    drawing = Drawing(WIDTH, 220)
    chart = LinePlot()
    chart.x, chart.y, chart.width, chart.height = 55, 30, WIDTH - 75, 160
    chart.data = [
        list(zip(ages, data['net_worths'])),
        list(zip(ages, data['magic_numbers'])),
    ]
    chart.lines[0].strokeColor = GREEN
    chart.lines[0].strokeWidth = 2.5
    chart.lines[1].strokeColor = INK
    chart.lines[1].strokeWidth = 1.5
    chart.lines[1].strokeDashArray = [5, 3]
    chart.yValueAxis.labelTextFormat = _short
    chart.yValueAxis.labels.fontSize = 8
    chart.xValueAxis.labels.fontSize = 8
    chart.xValueAxis.valueMin = ages[0]
    chart.xValueAxis.valueMax = ages[-1]
    chart.yValueAxis.valueMin = min(0, min(data['net_worths']))
    chart.yValueAxis.visibleGrid = True
    chart.yValueAxis.gridStrokeColor = MUTED
    drawing.add(chart)
    drawing.add(String(55, 200, 'Net worth vs. Magic Number', fontSize=10, fontName='Helvetica-Bold'))
    drawing.add(String(WIDTH / 2, 8, 'Age', fontSize=8, textAnchor='middle'))
    _legend(drawing, [(GREEN, 'Net worth'), (INK, 'Magic Number')], WIDTH - 140, 205)
    return drawing


def _cash_flow_chart(data):
    drawing = Drawing(WIDTH, 220)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 55, 30, WIDTH - 75, 160
    chart.data = [data['income'], data['expenses'], data['savings']]
    chart.categoryAxis.categoryNames = [str(a) for a in data['ages']]
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.angle = 0
    chart.categoryAxis.tickShift = 0
    if len(data['ages']) > 20:
        chart.categoryAxis.labelAxisMode = 'low'
        chart.categoryAxis.labels.fontSize = 6
    chart.valueAxis.labelTextFormat = _short
    chart.valueAxis.labels.fontSize = 8
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = MUTED
    chart.groupSpacing = 4
    chart.barSpacing = 0
    for i, color in enumerate((GREEN, ORANGE, PURPLE)):
        chart.bars[i].fillColor = color
        chart.bars[i].strokeColor = None
    drawing.add(chart)
    drawing.add(String(55, 200, 'Income, expenses and savings by year', fontSize=10, fontName='Helvetica-Bold'))
    _legend(drawing, [(GREEN, 'Income'), (ORANGE, 'Expenses'), (PURPLE, 'Savings')], WIDTH - 200, 205)
    return drawing


def build_plan_pdf(plan, fiplan, data):
    """Return the PDF bytes for a plan; fiplan is the PlanObject and data its chart_data()."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            title=f'{plan.plan_name} - FI Planner', author='FI Planner')
    styles = getSampleStyleSheet()
    title = ParagraphStyle('t', parent=styles['Title'], alignment=0, textColor=GREEN, fontSize=22, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], textColor=GREEN, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle('b', parent=styles['BodyText'], fontSize=10, leading=14)
    small = ParagraphStyle('s', parent=body, fontSize=8, textColor=colors.grey)
    label = ParagraphStyle('l', parent=small, textColor=colors.HexColor('#555555'))
    value = ParagraphStyle('v', parent=body, fontSize=15, leading=18, textColor=GREEN, fontName='Helvetica-Bold')

    on_track = bool(fiplan.fi_reached)
    story = [Paragraph(plan.plan_name, title),
             Paragraph(f'Financial independence plan &middot; current age {plan.current_age}, retiring at {plan.retirement_age}', small),
             Spacer(1, 10)]

    verdict = ('On track for financial independence.' if on_track
               else f'Not yet on track: {fiplan.funded_percent}% funded, a shortfall of {fiplan.funded_gap_display}.')
    verdict_table = Table([[Paragraph(f'<b>{verdict}</b>', body)]], colWidths=[WIDTH])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E6F2EC') if on_track else colors.HexColor('#FCEBE2')),
        ('LINEBEFORE', (0, 0), (0, -1), 4, GREEN if on_track else ORANGE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story += [verdict_table, Spacer(1, 10)]

    success = data.get('scenarios', {}).get('success_probability')
    kpis = [
        ('Projected net worth', fiplan.net_worths_last), ('Magic Number', fiplan.magic_numbers_last),
        ('FI age', fiplan.fi_age), ('Funded', f'{fiplan.funded_percent}%'),
        ('Avg. savings rate', f'{fiplan.average_savings_rate}%'), ('Coast FI age', fiplan.coast_fi_age),
        ('Withdraw rate', fiplan.drawdowns_last), ('Chance of reaching it', f'{success}%' if success is not None else 'N/A'),
    ]
    cells = [[Paragraph(name, label), Paragraph(str(val), value)] for name, val in kpis]
    rows = [[], []]
    for i, (name, val) in enumerate(cells):
        rows[i // 4].append([name, val])
    kpi_table = Table(rows, colWidths=[WIDTH / 4] * 4)
    kpi_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, MUTED), ('INNERGRID', (0, 0), (-1, -1), 0.5, MUTED),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story += [kpi_table, Spacer(1, 12), _net_worth_chart(data),
              Paragraph('Projections are estimates based on the assumptions in your plan and are not financial advice.', small),
              Spacer(1, 6), KeepTogether([Paragraph('Cash flow', h2), _cash_flow_chart(data)]),
              Paragraph('Year by year', h2)]

    header = ['Age', 'Income', 'Expenses', 'Savings', 'Net worth', 'Magic Number']
    table_rows = [header] + [
        [age, _money(inc), _money(exp), _money(sav), _money(nw), _money(mn)]
        for age, inc, exp, sav, nw, mn in zip(data['ages'], data['income'], data['expenses'], data['savings'],
                                              data['net_worths'], data['magic_numbers'])
    ]
    year_table = Table(table_rows, repeatRows=1, colWidths=[WIDTH * 0.1] + [WIDTH * 0.18] * 5)
    year_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F6F4')]),
        ('GRID', (0, 0), (-1, -1), 0.25, MUTED),
    ]))
    story.append(year_table)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.75 * inch, 0.4 * inch, 'FI Planner - fiplanner.app')
        canvas.drawRightString(letter[0] - 0.75 * inch, 0.4 * inch, f'Page {document.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
