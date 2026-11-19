"""Public guide articles for the /learn/ section. Bodies are trusted, hand-written HTML."""

ARTICLES = [
    {
        'slug': 'what-is-fire',
        'title': 'What is FIRE? Financial Independence, Retire Early explained',
        'summary': 'The basics of the FIRE movement: how it works, the main flavors and how to start.',
        'description': 'What FIRE (Financial Independence, Retire Early) means, how the savings-rate math works, the main types of FIRE, and how to find your own number.',
        'body': """
<p><strong>FIRE</strong> stands for <em>Financial Independence, Retire Early</em>. The idea is simple: save and invest enough that your portfolio can pay for your living costs indefinitely, so work becomes a choice rather than a requirement.</p>
<h2>How FIRE works</h2>
<p>Financial independence (FI) is reached when your investments can cover your annual expenses. A common rule of thumb is the <a href="/learn/fire-number-and-the-4-percent-rule/">4% rule</a>: if you withdraw 4% of your portfolio in the first year, adjusting for inflation afterwards, it has historically lasted 30 years or more. That works out to a target of about <strong>25 times your annual spending</strong>.</p>
<h2>Why savings rate matters most</h2>
<p>Your savings rate does two things at once: it builds the portfolio faster, and it shows how little you need to live on. Someone saving 10% of income needs roughly 40+ working years; someone saving 50% can get there in about 17 years, because they are both investing more and needing less.</p>
<h2>Types of FIRE</h2>
<ul>
<li><strong>Lean FIRE</strong>: a frugal lifestyle with a smaller target number.</li>
<li><strong>Fat FIRE</strong>: a more generous budget and a larger target.</li>
<li><strong>Barista FIRE</strong>: part-time work covers some costs so the portfolio can be smaller.</li>
<li><strong><a href="/learn/what-is-coast-fire/">Coast FIRE</a></strong>: you have already invested enough that growth alone reaches your goal by retirement age.</li>
</ul>
<h2>Where to start</h2>
<ol>
<li>Work out what you spend in a year.</li>
<li>Multiply by 25 to get your FI number.</li>
<li>Track how much you save and invest, and see how many years remain.</li>
</ol>
<p>The free <a href="/fire-calculator/">FIRE calculator</a> does this in seconds, and a full FI Planner plan adds taxes, income changes and a year-by-year timeline.</p>
""",
    },
    {
        'slug': 'what-is-coast-fire',
        'title': 'What is Coast FIRE? How to calculate your Coast FI number',
        'summary': 'Stop saving for retirement and let compounding finish the job. Here is how to find your number.',
        'description': 'Coast FIRE explained: what it is, the Coast FI number formula, a worked example and how it differs from full FIRE. Try the free Coast FIRE calculator.',
        'body': """
<p><strong>Coast FIRE</strong> means you have already invested enough that, even if you never add another dollar, your portfolio will grow to a full retirement amount by the time you plan to retire. You only need to earn enough to cover current living costs, which opens the door to lower-stress or lower-paying work.</p>
<h2>The Coast FI number formula</h2>
<p>Your Coast FI number is the amount you need invested <em>today</em>:</p>
<p class="fs-5"><code>Coast number = FI number &divide; (1 + real return) <sup>years until retirement</sup></code></p>
<p>Use a real (after-inflation) return, such as 5%, so everything stays in today's dollars.</p>
<h2>Worked example</h2>
<p>Suppose you spend $50,000 a year, so your FI number is $50,000 &times; 25 = <strong>$1,250,000</strong>. You are 30 and want to retire at 60 (30 years) and assume a 5% real return. Growth over 30 years multiplies money by about 4.32, so your Coast FI number is $1,250,000 &divide; 4.32 &asymp; <strong>$289,000</strong>. If you have that invested at 30, you are Coast FI.</p>
<h2>Coast FIRE vs. full FIRE</h2>
<p>With full FIRE you keep saving until you can stop working. With Coast FIRE you stop <em>saving</em> but keep working, at least enough to pay current bills. Many people reach Coast FI years before they could fully retire.</p>
<h2>Things to remember</h2>
<ul>
<li>Returns are not guaranteed. Build in a margin of safety.</li>
<li>Your expenses at retirement may differ from today's.</li>
<li>Taxes, healthcare and Social Security can all change the picture.</li>
</ul>
<p>Try the <a href="/coast-fire-calculator/">Coast FIRE calculator</a> with your own numbers, or build a full plan in FI Planner to see your Coast FI age on a chart.</p>
""",
    },
    {
        'slug': 'fire-number-and-the-4-percent-rule',
        'title': 'Your FIRE number and the 4% rule, explained',
        'summary': 'Where the 25x rule comes from, what it assumes and when to use a different withdrawal rate.',
        'description': 'How to calculate your FIRE number with the 4% rule (25x annual expenses), where the rule comes from, its limits, and when to use a lower withdrawal rate.',
        'body': """
<p>Your <strong>FIRE number</strong> (or FI number) is the portfolio size at which you can live off your investments. The most common way to estimate it is the 4% rule.</p>
<h2>The formula</h2>
<p class="fs-5"><code>FIRE number = annual expenses &divide; withdrawal rate</code></p>
<p>At a 4% withdrawal rate, that is annual expenses &times; 25. Spend $40,000 a year and you need $1,000,000; spend $80,000 and you need $2,000,000.</p>
<h2>Where the 4% rule comes from</h2>
<p>The rule is based on the 1998 &ldquo;Trinity study&rdquo;, which tested withdrawal rates against historical US stock and bond returns. A 4% initial withdrawal, raised each year with inflation, survived 30-year periods in almost every historical scenario.</p>
<h2>Limits to know about</h2>
<ul>
<li>Early retirees need money to last longer than 30 years, so many use <strong>3.25% to 3.5%</strong> instead.</li>
<li>Past results do not guarantee future returns.</li>
<li>Poor returns early in retirement (&ldquo;sequence risk&rdquo;) do the most damage.</li>
<li>Taxes, healthcare and one-off costs are not in the simple formula.</li>
</ul>
<h2>Quick reference</h2>
<table class="table table-sm">
<thead><tr><th>Annual spending</th><th>3.5% rate</th><th>4% rate</th></tr></thead>
<tbody>
<tr><td>$30,000</td><td>$857,000</td><td>$750,000</td></tr>
<tr><td>$50,000</td><td>$1,429,000</td><td>$1,250,000</td></tr>
<tr><td>$80,000</td><td>$2,286,000</td><td>$2,000,000</td></tr>
</tbody>
</table>
<p>Enter your own spending in the <a href="/fire-calculator/">FIRE calculator</a> to see your number and how many years until you reach it.</p>
""",
    },
    {
        'slug': 'lean-fat-barista-coast-fire',
        'title': 'Lean, Fat, Barista and Coast FIRE: which type fits you?',
        'summary': 'A side-by-side look at the four most popular flavors of financial independence.',
        'description': 'Compare Lean FIRE, Fat FIRE, Barista FIRE and Coast FIRE: what each means, who they suit and the trade-offs of each approach.',
        'body': """
<p>There is no single way to pursue financial independence. These are the four most common approaches.</p>
<h2>Lean FIRE</h2>
<p>Living on a modest budget so your target number is smaller. It can get you out of the workforce sooner, but leaves less room for surprises.</p>
<h2>Fat FIRE</h2>
<p>A comfortable or generous budget funded by a larger portfolio. It usually takes longer and often relies on a high income.</p>
<h2>Barista FIRE</h2>
<p>You leave a demanding career for part-time or lower-stress work that covers some expenses (often health insurance). The portfolio covers the rest, so it can be smaller than for full FIRE.</p>
<h2>Coast FIRE</h2>
<p>You have invested enough that growth alone will reach your retirement number, so you only need to cover today's expenses. See <a href="/learn/what-is-coast-fire/">What is Coast FIRE?</a></p>
<h2>Comparing them</h2>
<table class="table table-sm">
<thead><tr><th>Type</th><th>Still working?</th><th>Still saving?</th><th>Best for</th></tr></thead>
<tbody>
<tr><td>Lean</td><td>No</td><td>No</td><td>Low-cost lifestyles</td></tr>
<tr><td>Fat</td><td>No</td><td>No</td><td>High earners wanting comfort</td></tr>
<tr><td>Barista</td><td>Part-time</td><td>Maybe</td><td>Wanting flexibility sooner</td></tr>
<tr><td>Coast</td><td>Yes</td><td>No</td><td>Early savers who want less pressure</td></tr>
</tbody>
</table>
<p>You do not need to pick one forever. Build a plan in FI Planner and use the what-if tools to see how each path changes your timeline. <a href="/signup/">Create a free account</a> to start.</p>
""",
    },
    {
        'slug': 'retirement-expenses-and-healthcare-costs',
        'title': 'Expenses and healthcare costs in retirement: what to plan for',
        'summary': 'How spending changes after you stop working, and how to budget for health insurance before and after Medicare.',
        'description': 'What to expect for living expenses and healthcare costs in early retirement, including health insurance before Medicare, Medicare costs, long-term care and how to budget for them.',
        'body': """
<p>Your <a href="/learn/fire-number-and-the-4-percent-rule/">FIRE number</a> is only as good as the spending figure behind it. Two questions matter most: what will everyday life cost after you stop working, and how will you pay for healthcare?</p>
<h2>How spending changes in retirement</h2>
<p>Some costs usually fall: commuting, work clothes, payroll taxes and retirement contributions. Others often rise: travel, hobbies, healthcare and the simple fact that you have more free time. A good starting point is your current spending minus work-related costs, plus a realistic allowance for the things you plan to do with your time.</p>
<ul>
<li><strong>Housing</strong>: is the mortgage paid off? Property tax, insurance and maintenance never go away.</li>
<li><strong>Food, transport and utilities</strong>: usually stable.</li>
<li><strong>Travel and leisure</strong>: often highest in the first years.</li>
<li><strong>Taxes</strong>: withdrawals from pre-tax accounts are taxable income.</li>
<li><strong>Buffer</strong>: add 10% or so for the unexpected.</li>
</ul>
<h2>Healthcare before Medicare (US)</h2>
<p>If you retire before 65, you need your own health insurance. Common options are:</p>
<ul>
<li><strong>ACA marketplace plans</strong>: premiums can be reduced by subsidies that depend on your taxable income, so planning how much income you show can matter a lot.</li>
<li><strong>COBRA</strong>: continues your employer plan for a limited time, usually at full cost.</li>
<li><strong>A spouse's plan</strong>, if available.</li>
</ul>
<p>Rules and subsidy levels change, so check current rules on healthcare.gov before you rely on them.</p>
<h2>Healthcare after 65</h2>
<p>Medicare starts at 65, but it is not free. Expect premiums, deductibles and copays, and possibly supplemental coverage. Fidelity's annual estimate for a 65-year-old retiree's lifetime healthcare costs has been well into six figures per person, and that excludes long-term care.</p>
<h2>Long-term care</h2>
<p>Nursing or in-home care is expensive and not covered by regular health insurance. Options include long-term care insurance, hybrid life policies, or simply holding extra savings.</p>
<h2>How to build it into your plan</h2>
<ol>
<li>Add a separate healthcare line to your retirement budget.</li>
<li>Use a higher figure before 65 if you will buy your own insurance.</li>
<li>Contribute to an HSA while you are eligible. Money used for qualified medical expenses comes out tax-free.</li>
<li>Test a higher spending number and see how your FI date changes.</li>
</ol>
<p>In FI Planner you can enter different expenses for different life stages and see your retirement date move. <a href="/signup/">Create a free account</a> to try it, or start with the <a href="/fire-calculator/">FIRE calculator</a>.</p>
<p class="small text-muted">General information only, not medical, insurance or financial advice. Costs and rules vary by country and change over time.</p>
""",
    },
    {
        'slug': 'having-kids-on-the-path-to-fire',
        'title': 'Having kids on the path to FIRE: costs, trade-offs and planning',
        'summary': 'What children really cost, how they change your FI number and timeline, and how to plan for them.',
        'description': 'How having children affects your path to FIRE: the real cost of raising a child, childcare and college, how it changes your FI number, and practical ways to plan.',
        'body': """
<p>Children are the biggest change most people make to their finances, and they do not have to end your FIRE plans. They do change the numbers, so it helps to plan for them rather than be surprised.</p>
<h2>What kids cost</h2>
<p>Estimates for raising a child to age 18 in the US commonly land in the low-to-mid six figures per child, before college. Costs vary hugely by where you live and how you parent. The big categories are:</p>
<ul>
<li><strong>Housing</strong>: often a bigger home or a better school district.</li>
<li><strong>Childcare</strong>: frequently the largest expense in the early years, and can rival a mortgage.</li>
<li><strong>Food, healthcare and activities</strong>.</li>
<li><strong>College</strong>: optional to fund, but worth deciding on early.</li>
</ul>
<h2>How kids change your FIRE math</h2>
<p>Higher spending raises your <a href="/learn/fire-number-and-the-4-percent-rule/">FIRE number</a>: every extra $1,000 a month of spending adds about $300,000 to your target at a 4% withdrawal rate. At the same time you may save less while costs are highest, which pushes the date out. Many families see their timeline stretch by several years.</p>
<p>It can also help: when children are grown, spending often drops again, and some families reach <a href="/learn/what-is-coast-fire/">Coast FIRE</a> in the early years and keep working at a gentler pace.</p>
<h2>Ways to plan</h2>
<ol>
<li><strong>Model it before it happens.</strong> Add the expected extra costs, and any reduced income while a parent takes leave, to your plan.</li>
<li><strong>Plan the childcare years.</strong> Dependent-care FSAs and tax credits may reduce the cost, depending on where you live.</li>
<li><strong>Decide on education early.</strong> A 529 plan or similar account lets money grow tax-advantaged, but you do not have to fully fund college.</li>
<li><strong>Keep your own retirement on track.</strong> Children can borrow for college, but you cannot borrow for retirement.</li>
<li><strong>Review yearly.</strong> Costs and income change, so update your plan as they do.</li>
</ol>
<h2>Try it yourself</h2>
<p>The what-if tools in FI Planner let you add new expenses and see how your FI age changes. <a href="/signup/">Create a free account</a> and compare a plan with and without children.</p>
<p class="small text-muted">General information only, not financial or tax advice. Child-related costs and tax benefits vary by country and change over time.</p>
""",
    },
]

ARTICLES_BY_SLUG = {a['slug']: a for a in ARTICLES}
