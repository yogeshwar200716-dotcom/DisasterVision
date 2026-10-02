import math
import re
from pathlib import Path
from PIL import Image, ImageChops

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'satellite_data'
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


def year_from_filename(path):
    m = re.search(r'(?:^|[-_ ])(\d{4})(?:$|[-_ .])', Path(path).stem)
    return int(m.group(1)) if m else None


def image_files(folder):
    result = []
    folder = Path(folder)
    if not folder.is_dir():
        return result
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            y = year_from_filename(p)
            if y is not None:
                result.append((y, p))
    return sorted(result, key=lambda x: x[0])


LOCATION_ORDER = [
    'BEAR, ALASKA',
    'Breiðamerkurjökull, Iceland',
    'Brunt Ice Shelf, Antarctica',
    'CULOMBIA',
    'Kilimanjaro,tanzania',
    'Petermann, greenland',
    'Svalbard, NORWAY',
    'VERDI,ANTARCTICA',
]

def discover_options():
    # Expose the actual folder names, including folders that currently contain
    # no dated images. This keeps the Location selector identical to the
    # server's satellite_data folder structure.
    options = {}
    if not DATA_DIR.is_dir():
        return options
    for disaster_dir in sorted(DATA_DIR.iterdir(), key=lambda p: p.name.casefold()):
        if not disaster_dir.is_dir():
            continue
        folders = [p for p in disaster_dir.iterdir() if p.is_dir()]
        by_name = {p.name: p.name for p in folders}
        ordered = [name for name in LOCATION_ORDER if name in by_name]
        ordered.extend(sorted((name for name in by_name if name not in LOCATION_ORDER), key=str.casefold))
        if ordered:
            options[disaster_dir.name] = ordered
    if 'GLACIER' in options:
        options = {'GLACIER': options['GLACIER'], **{k:v for k,v in options.items() if k != 'GLACIER'}}
    return options


def calculate_change(image_a, image_b):
    with Image.open(image_a).convert('RGB') as a, Image.open(image_b).convert('RGB') as b:
        a = a.resize(b.size)
        diff = ImageChops.difference(a, b)
        total_pixels = b.width * b.height
        # Per-pixel average difference > 20, matching the project's original threshold.
        significant = sum(1 for r,g,bb in diff.getdata() if (r+g+bb)/3.0 > 20)
    return round((significant / total_pixels) * 100.0, 2) if total_pixels else 0.0


def regression_rate(changes):
    # changes: [(year, percent_change_to_latest), ...]
    # Use years-before-latest as x, so an increasing historical change trend
    # produces a positive annual rate.
    if len(changes) < 2:
        return 0.0, None
    latest_year = max(y for y, _ in changes)
    xs = [float(latest_year - y) for y, _ in changes]
    ys = [float(c) for _, c in changes]
    xbar = sum(xs) / len(xs); ybar = sum(ys) / len(ys)
    denom = sum((x-xbar)**2 for x in xs)
    if denom == 0:
        return 0.0, None
    slope = sum((x-xbar)*(y-ybar) for x,y in zip(xs,ys)) / denom
    intercept = ybar - slope*xbar
    return max(0.0, slope), intercept


def predict(changes, future_year, latest_year):
    slope, intercept = regression_rate(changes)
    # Change is measured relative to the latest image, so anchor the forecast at 0 at latest_year.
    if slope <= 0:
        rate = 0.0
    else:
        rate = slope
    years_ahead = future_year - latest_year
    predicted = max(0.0, min(100.0, rate * years_ahead))
    if predicted >= 40:
        risk = 'HIGH'
    elif predicted >= 20:
        risk = 'MODERATE'
    else:
        risk = 'LOW'
    if rate > 0:
        moderate_year = latest_year + math.ceil(20.0 / rate)
        high_year = latest_year + math.ceil(40.0 / rate)
        window = f'{moderate_year} – {high_year}'
        window_status = 'ESTIMATED_WINDOW'
    else:
        moderate_year = high_year = None
        window = 'Not reliably predictable from the stored trend'
        window_status = 'NO_INCREASING_TREND'
    return {
        'future_year': future_year,
        'latest_historical_year': latest_year,
        'predicted_change': round(predicted, 2),
        'risk': risk,
        'annual_change_rate': round(rate, 4),
        'equation': f'change(t) = {rate:.4f} × (t - {latest_year})',
        'disaster_window': {
            'status': window_status,
            'estimated_from_year': moderate_year,
            'estimated_to_year': high_year,
            'moderate_risk_year': moderate_year,
            'high_risk_year': high_year,
            'estimated_disaster_year': high_year,
            'window': window,
            'message': 'Model-derived interval from the stored satellite-image trend; it is not a guaranteed physical disaster date.',
            'thresholds': {'moderate': 20, 'high': 40},
        },
    }


def analyze(disaster, location, future_year):
    options = discover_options()
    if disaster not in options or location not in options[disaster]:
        raise ValueError('The selected disaster/location is not available in the server dataset.')
    folder = DATA_DIR / disaster / location
    files = image_files(folder)
    if not files:
        raise ValueError(f'No dated satellite images are available for {location}.')
    latest_year, latest_image = files[-1]
    if future_year <= latest_year:
        raise ValueError(f'Enter a future year after {latest_year} for {location}.')
    changes = [[y, calculate_change(p, latest_image)] for y,p in files]
    prediction = predict(changes, future_year, latest_year)
    prediction['baseline_image'] = latest_image.name
    prediction['disaster'] = disaster
    prediction['location'] = location
    risk = prediction['risk']
    return {
        'future_year': future_year,
        'datasets_found': 1,
        'datasets_analyzed': 1,
        'overall': {'risk': risk, 'predicted_change': prediction['predicted_change'], 'location': location, 'disaster': disaster},
        'results': [{
            'disaster': disaster,
            'location': location,
            'status': 'OK',
            'baseline_image': latest_image.name,
            'changes': changes,
            'prediction': prediction,
        }],
        'model_note': 'The latest dated image in the selected server folder is the baseline; earlier images are compared against it.',
    }
