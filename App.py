from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import re
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
APP_NAME = "TRACE"
VERSION = "2.0"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TRACE · Black & Gold</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0a0a;
            color: #c8c0b0;
            font-family: 'Inter', 'Segoe UI', 'Georgia', serif;
            padding: 40px 20px;
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 940px;
            width: 100%;
            background: #111111;
            padding: 38px 42px;
            border-radius: 12px;
            border: 1px solid #2a2a1a;
            box-shadow: 0 0 40px rgba(212, 175, 55, 0.06), 0 8px 32px rgba(0,0,0,0.9);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            border-bottom: 1px solid #2a2a1a;
            padding-bottom: 14px;
            margin-bottom: 28px;
            flex-wrap: wrap;
        }
        .logo {
            font-size: 32px;
            font-weight: 400;
            letter-spacing: 6px;
            color: #d4af37;
            text-shadow: 0 0 20px rgba(212, 175, 55, 0.15);
        }
        .logo span { color: #f0d080; }
        .tagline {
            font-size: 12px;
            color: #6a6a4a;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-top: 2px;
        }
        .version {
            font-size: 12px;
            color: #4a4a2a;
            letter-spacing: 1px;
            border: 1px solid #2a2a1a;
            padding: 4px 14px;
            border-radius: 30px;
        }
        .field-group {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 6px;
        }
        .field-group input {
            flex: 1;
            min-width: 200px;
            padding: 16px 20px;
            background: #0a0a08;
            border: 1px solid #2a2a1a;
            border-radius: 8px;
            color: #e8ddd0;
            font-size: 16px;
            font-family: 'Inter', sans-serif;
            outline: none;
            transition: border 0.3s, box-shadow 0.3s;
        }
        .field-group input:focus {
            border-color: #d4af37;
            box-shadow: 0 0 20px rgba(212, 175, 55, 0.08);
        }
        .field-group input::placeholder { color: #3a3a2a; }
        .field-group button {
            padding: 16px 38px;
            background: #d4af37;
            border: none;
            border-radius: 8px;
            color: #0a0a08;
            font-weight: 700;
            font-size: 14px;
            letter-spacing: 2px;
            cursor: pointer;
            transition: background 0.3s, box-shadow 0.3s;
            text-transform: uppercase;
            font-family: 'Inter', sans-serif;
        }
        .field-group button:hover {
            background: #e8c84a;
            box-shadow: 0 0 30px rgba(212, 175, 55, 0.25);
        }
        .field-group button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .error {
            background: #141410;
            border-left: 4px solid #b8942a;
            padding: 14px 20px;
            border-radius: 6px;
            margin-top: 18px;
            color: #c8b080;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
        }
        .section {
            background: #0d0d0a;
            padding: 18px 22px;
            border-radius: 8px;
            margin-top: 22px;
            border-left: 3px solid #d4af37;
            box-shadow: inset 0 0 30px rgba(0,0,0,0.4);
            animation: fadeIn 0.4s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .section-title {
            font-weight: 400;
            font-size: 11px;
            letter-spacing: 2.5px;
            color: #d4af37;
            margin-bottom: 12px;
            text-transform: uppercase;
            border-bottom: 1px solid #1a1a10;
            padding-bottom: 8px;
        }
        .row {
            display: flex;
            flex-wrap: wrap;
            gap: 4px 24px;
            padding: 3px 0;
        }
        .row-item {
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            color: #b0a898;
        }
        .row-item strong {
            color: #d4af37;
            font-weight: 500;
            margin-right: 6px;
            letter-spacing: 0.5px;
        }
        .badge {
            display: inline-block;
            background: #141410;
            padding: 2px 16px;
            border-radius: 30px;
            font-size: 13px;
            font-family: 'Inter', sans-serif;
            border: 1px solid #2a2a1a;
            margin: 2px 4px 2px 0;
            color: #b0a090;
        }
        .badge-valid { border-color: #d4af37; color: #d4af37; }
        .badge-invalid { border-color: #4a3a2a; color: #6a5a4a; }
        .social-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .social-grid a {
            background: #0d0d0a;
            padding: 6px 20px;
            border-radius: 30px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            color: #b0a898;
            text-decoration: none;
            border: 1px solid #2a2a1a;
            transition: 0.25s;
        }
        .social-grid a:hover {
            border-color: #d4af37;
            color: #d4af37;
            box-shadow: 0 0 20px rgba(212, 175, 55, 0.06);
        }
        .link-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px 16px;
            margin-top: 4px;
        }
        .link-list a {
            color: #8a7a5a;
            text-decoration: none;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            border-bottom: 1px dotted #1a1a10;
            padding-bottom: 2px;
            transition: 0.25s;
        }
        .link-list a:hover {
            color: #d4af37;
            border-bottom-color: #d4af37;
        }
        hr {
            border: none;
            border-top: 1px solid #1a1a10;
            margin: 24px 0 8px 0;
        }
        .footer {
            font-size: 11px;
            color: #3a3a2a;
            font-family: 'Inter', sans-serif;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            margin-top: 4px;
            letter-spacing: 0.5px;
        }
        .hidden { display: none !important; }
        .loader {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #0a0a08;
            border-top-color: #d4af37;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
            margin-left: 10px;
            vertical-align: middle;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        @media (max-width: 600px) {
            .container { padding: 18px; }
            .field-group input { min-width: 100%; }
            .header { flex-direction: column; gap: 6px; align-items: flex-start; }
            .logo { font-size: 26px; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <div class="logo">TR<span>A</span>CE</div>
            <div class="tagline">след. данные. идентификация.</div>
        </div>
        <div class="version">v{{ version }}</div>
    </div>
    <form method="POST">
        <div class="field-group">
            <input type="text" name="phone" placeholder="+7 999 123 45 67" value="{{ phone or '' }}" required>
            <button type="submit">Scan</button>
        </div>
    </form>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    {% if result %}
        <div class="section">
            <div class="section-title">Number Profile</div>
            <div class="row">
                <span class="row-item"><strong>Raw</strong> {{ result.raw }}</span>
                <span class="row-item"><strong>E.164</strong> {{ result.e164 or '—' }}</span>
                <span class="row-item"><strong>Country</strong> {{ result.country or '—' }}</span>
                <span class="row-item"><strong>Region</strong> {{ result.region or '—' }}</span>
                <span class="row-item"><strong>Carrier</strong> {{ result.carrier or '—' }}</span>
                <span class="row-item"><strong>Timezone</strong> {{ result.timezone or '—' }}</span>
            </div>
            <div class="row" style="margin-top:4px;">
                <span class="row-item">
                    <strong>Valid</strong>
                    <span class="badge {% if result.valid %}badge-valid{% else %}badge-invalid{% endif %}">
                        {{ 'Yes' if result.valid else 'No' }}
                    </span>
                </span>
                <span class="row-item">
                    <strong>Possible</strong>
                    <span class="badge {% if result.possible %}badge-valid{% else %}badge-invalid{% endif %}">
                        {{ 'Yes' if result.possible else 'No' }}
                    </span>
                </span>
            </div>
        </div>
        {% if result.truecaller_name %}
        <div class="section" style="border-left-color: #c8a84a;">
            <div class="section-title">Truecaller</div>
            <div style="font-size:16px; font-weight:400; color:#d4af37; font-family:'Georgia', serif;">
                {{ result.truecaller_name }}
            </div>
        </div>
        {% endif %}
        {% if result.spytox %}
        <div class="section" style="border-left-color: #b8983a;">
            <div class="section-title">Spytox</div>
            <div>
                {% for key, value in result.spytox.items() %}
                    <span class="badge" style="border-color:#3a3a2a;">{{ key }}: {{ value }}</span>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        {% if result.breaches %}
        <div class="section" style="border-left-color: #8a6a2a;">
            <div class="section-title">Breaches</div>
            <div>
                {% for b in result.breaches %}
                    <span class="badge" style="border-color:#3a2a1a;">{{ b }}</span>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        {% if result.social %}
        <div class="section" style="border-left-color: #a08030;">
            <div class="section-title">Active Profiles</div>
            <div class="social-grid">
                {% for name, url in result.social.items() %}
                    <a href="{{ url }}" target="_blank">{{ name }}</a>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        <div class="section" style="border-left-color: #6a5a3a;">
            <div class="section-title">Search Queries</div>
            <div class="link-list">
                {% for link in result.search_links %}
                    <a href="{{ link }}" target="_blank">Search</a>
                {% endfor %}
            </div>
        </div>
        <hr>
        <div class="footer">
            <span>TRACE v{{ version }}</span>
            <span>public sources · local</span>
        </div>
    {% endif %}
</div>
</body>
</html>
"""

def clean_phone(phone):
    return re.sub(r'\D', '', phone)

def check_truecaller(phone):
    try:
        url = f"https://www.truecaller.com/search/{phone}"
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, 'lxml')
        name_tag = soup.find("span", class_="name")
        return name_tag.text.strip() if name_tag else None
    except:
        return None

def check_spytox(phone):
    try:
        url = f"https://www.spytox.com/search?q={phone}"
        r = requests.get(url, timeout=8)
        soup = BeautifulSoup(r.text, 'lxml')
        data = {}
        for item in soup.find_all("div", class_="result-item"):
            key = item.find("span", class_="label")
            val = item.find("span", class_="value")
            if key and val:
                data[key.text.strip()] = val.text.strip()
        return data
    except:
        return {}

def check_breaches(phone):
    results = []
    try:
        r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{phone}", timeout=8)
        if r.status_code == 200:
            for b in r.json()[:5]:
                results.append(b.get("Name"))
    except:
        pass
    try:
        r = requests.get(f"https://leakcheck.net/api/public?check={phone}", timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data.get("found"):
                results.append("LeakCheck")
    except:
        pass
    return results

def search_social(phone):
    social_links = {
        "VK": f"https://vk.com/search?c[phone]={phone}",
        "OK": f"https://ok.ru/search?q={phone}",
        "Facebook": f"https://www.facebook.com/search/top/?q={phone}",
        "Twitter": f"https://twitter.com/search?q={phone}",
        "Instagram": f"https://www.google.com/search?q=site:instagram.com+{phone}",
        "Telegram": f"https://t.me/{phone}",
        "WhatsApp": f"https://api.whatsapp.com/send?phone={phone}"
    }
    found = {}
    for name, url in social_links.items():
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.text) > 1000:
                found[name] = url
        except:
            pass
    return found

def parse_phone(phone_raw):
    phone = clean_phone(phone_raw)
    result = {
        "raw": phone_raw,
        "clean": phone,
        "e164": "",
        "country": "",
        "region": "",
        "carrier": "",
        "timezone": "",
        "valid": False,
        "possible": False,
        "truecaller_name": None,
        "spytox": {},
        "breaches": [],
        "social": {},
        "search_links": []
    }

    try:
        parsed = phonenumbers.parse(phone_raw, None)
        if phonenumbers.is_valid_number(parsed):
            result["valid"] = True
            result["e164"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            result["country"] = geocoder.country_name_for_number(parsed, "en")
            result["region"] = geocoder.description_for_number(parsed, "en")
            result["carrier"] = carrier.name_for_number(parsed, "en")
            tz = timezone.time_zones_for_number(parsed)
            result["timezone"] = ", ".join(tz) if tz else ""
            result["possible"] = phonenumbers.is_possible_number(parsed)
    except:
        pass

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_true = executor.submit(check_truecaller, phone)
        future_spy = executor.submit(check_spytox, phone)
        future_breach = executor.submit(check_breaches, phone)
        future_social = executor.submit(search_social, phone)

        result["truecaller_name"] = future_true.result()
        result["spytox"] = future_spy.result()
        result["breaches"] = future_breach.result()
        result["social"] = future_social.result()

    result["search_links"] = [
        f"https://www.google.com/search?q=%22{phone}%22",
        f"https://yandex.ru/search/?text={phone}",
        f"https://duckduckgo.com/?q={phone}",
        f"https://www.bing.com/search?q={phone}"
    ]

    return result

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        phone = request.form.get('phone', '')
        if not phone or len(clean_phone(phone)) < 7:
            return render_template_string(HTML_TEMPLATE, error="требуется минимум 7 цифр", version=VERSION)
        data = parse_phone(phone)
        return render_template_string(HTML_TEMPLATE, result=data, phone=phone, version=VERSION)
    return render_template_string(HTML_TEMPLATE, version=VERSION)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
