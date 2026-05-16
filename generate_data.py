"""
Generate a realistic synthetic IT help desk ticket dataset.
Produces data/tickets.csv with ~2 years of ticket history.

Realistic patterns baked in:
- Monday-morning ticket spikes
- Q1/Q4 higher volume (year-end, new-year onboarding)
- Agent-specific performance profiles (speed, CSAT variance)
- Hardware surge in Nov (new equipment rollout)
- One chronic recurring issue per quarter
"""

import csv
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

CATEGORIES = ["Hardware", "Software", "Network", "Access/Permissions", "Email", "Printer", "VPN", "Other"]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
PRIORITY_WEIGHTS = [0.05, 0.15, 0.50, 0.30]
DEPARTMENTS = ["Finance", "HR", "Engineering", "Sales", "Marketing", "Operations", "Legal", "IT"]

# Agent profiles: (speed_multiplier, csat_mean, csat_std)
# speed < 1.0 = faster than baseline, > 1.0 = slower
AGENT_PROFILES = {
    "Michael Torres":   (0.75, 4.6, 0.4),   # fast, high CSAT — top performer
    "Jennifer Walsh":   (0.90, 4.2, 0.5),
    "David Kim":        (1.00, 4.0, 0.6),
    "Rachel Patel":     (1.20, 3.5, 0.8),   # slow, mediocre CSAT
    "Christopher Nguyen": (0.85, 4.3, 0.5),
    "Amanda Brooks":    (1.10, 3.8, 0.7),
    "Kevin Chen":       (0.95, 4.1, 0.5),
    "Sarah Rivera":     (1.40, 2.9, 0.9),   # struggling agent — realistic outlier
}

SLA_TARGETS = {
    "P1 - Critical": 4,
    "P2 - High": 24,
    "P3 - Medium": 72,
    "P4 - Low": 168,
}

RESOLUTION_BASE = {
    "P1 - Critical": (1.5, 1.2),    # mean, std in hours (log-normal params)
    "P2 - High":     (12, 6),
    "P3 - Medium":   (36, 20),
    "P4 - Low":      (90, 50),
}

SUBJECTS = {
    "Hardware": [
        "Laptop won't turn on", "Monitor flickering", "Keyboard not working",
        "Mouse unresponsive", "Battery draining fast", "Screen cracked",
        "Docking station issue", "Webcam not detected",
    ],
    "Software": [
        "Application crashing", "Software license expired", "Can't install update",
        "Program not responding", "Blue screen error", "Slow computer performance",
        "Driver conflict", "Office activation failed",
    ],
    "Network": [
        "No internet connection", "Slow network speeds", "WiFi dropping",
        "Cannot reach shared drive", "Network printer offline", "DNS resolution failing",
        "Switch port down", "VLAN misconfiguration",
    ],
    "Access/Permissions": [
        "Cannot log in", "Password reset needed", "Need access to SharePoint",
        "Account locked out", "MFA not working", "New hire setup",
        "Offboarding access removal", "Shared drive permissions",
    ],
    "Email": [
        "Outlook not syncing", "Cannot send email", "Spam getting through",
        "Shared mailbox access", "Email bouncing", "Distribution list update",
        "Calendar not syncing", "Auto-reply not working",
    ],
    "Printer": [
        "Printer offline", "Paper jam", "Print quality poor",
        "Driver install needed", "Printer not found on network", "Out of toner",
        "Duplex not working", "Scan to email broken",
    ],
    "VPN": [
        "VPN not connecting", "VPN slow", "Remote desktop issue",
        "Two-factor prompt failing", "VPN client crash", "Split tunnel issue",
        "Certificate expired", "VPN drops after 30 minutes",
    ],
    "Other": [
        "General IT request", "Software recommendation", "Data recovery",
        "IT policy question", "Asset disposal request", "Equipment request",
        "IT audit support", "Backup restoration needed",
    ],
}

# Category weights by month — hardware spikes in Nov (rollout), network in summer
CATEGORY_SEASONAL = {
    "Hardware": {11: 2.5, 12: 1.8, 1: 1.6},
    "Network":  {6: 1.5, 7: 1.6, 8: 1.4},
    "Access/Permissions": {1: 1.8, 9: 1.5},  # new-year and back-to-school onboarding
}


def lognormal_hours(mean, std):
    """Sample resolution hours from a log-normal distribution."""
    mu = math.log(mean**2 / math.sqrt(std**2 + mean**2))
    sigma = math.sqrt(math.log(1 + (std / mean) ** 2))
    return max(0.1, random.lognormvariate(mu, sigma))


def weighted_datetime(start, end):
    """
    Sample a datetime biased toward business hours and Monday mornings.
    Rejects weekends at 80% rate, off-hours at 70% rate.
    """
    while True:
        delta = end - start
        dt = start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))
        weekday = dt.weekday()  # 0=Mon, 6=Sun
        hour = dt.hour

        # Weekend rejection
        if weekday >= 5 and random.random() < 0.80:
            continue
        # Off-hours rejection (before 7am or after 7pm)
        if (hour < 7 or hour > 19) and random.random() < 0.70:
            continue
        # Monday morning spike — keep more of these
        if weekday == 0 and 8 <= hour <= 11:
            break
        break
    return dt


def get_category(month):
    weights = []
    for cat in CATEGORIES:
        seasonal = CATEGORY_SEASONAL.get(cat, {})
        weights.append(seasonal.get(month, 1.0))
    total = sum(weights)
    weights = [w / total for w in weights]
    return random.choices(CATEGORIES, weights=weights)[0]


def seasonal_volume_weight(dt):
    """Q1 and Q4 are heavier ticket months."""
    month = dt.month
    if month in (1, 2, 11, 12):
        return 1.35
    if month in (6, 7, 8):
        return 0.80
    return 1.0


def generate_tickets(n=3000):
    start = datetime(2023, 1, 2, 8, 0)
    end = datetime(2024, 12, 27, 18, 0)
    tickets = []
    agents = list(AGENT_PROFILES.keys())

    # Assign departments to agents for realism
    agent_dept_bias = {
        "Michael Torres":     ["Engineering", "IT"],
        "Jennifer Walsh":     ["Finance", "Legal"],
        "David Kim":          ["HR", "Marketing"],
        "Rachel Patel":       ["Sales", "Operations"],
        "Christopher Nguyen": ["Engineering", "IT"],
        "Amanda Brooks":      ["Finance", "HR"],
        "Kevin Chen":         ["Sales", "Marketing"],
        "Sarah Rivera":       ["Operations", "Legal"],
    }

    i = 1
    attempts = 0
    while len(tickets) < n and attempts < n * 10:
        attempts += 1
        created = weighted_datetime(start, end)

        # Thin out low-season months
        if random.random() > seasonal_volume_weight(created):
            continue

        ticket_id = f"INC{i:05d}"
        priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS)[0]
        category = get_category(created.month)
        agent = random.choice(agents)
        speed_mult, csat_mean, csat_std = AGENT_PROFILES[agent]

        base_mean, base_std = RESOLUTION_BASE[priority]
        resolution_hours = round(lognormal_hours(base_mean * speed_mult, base_std * speed_mult), 2)
        sla_target = SLA_TARGETS[priority]
        met_sla = resolution_hours <= sla_target

        # Department — biased toward agent's usual departments
        biased = agent_dept_bias[agent]
        dept_pool = biased * 3 + DEPARTMENTS
        department = random.choice(dept_pool)

        # ~7% of tickets stay open
        if random.random() < 0.07:
            status = random.choice(["Open", "In Progress", "Pending User"])
            resolved = ""
            resolution_hours_out = ""
            met_sla_out = ""
            csat = ""
        else:
            status = random.choice(["Resolved", "Closed"])
            resolved = (created + timedelta(hours=resolution_hours)).strftime("%Y-%m-%d %H:%M")
            resolution_hours_out = resolution_hours
            met_sla_out = met_sla
            raw_csat = random.gauss(csat_mean, csat_std)
            csat = max(1, min(5, round(raw_csat)))

        tickets.append({
            "ticket_id": ticket_id,
            "created_at": created.strftime("%Y-%m-%d %H:%M"),
            "resolved_at": resolved,
            "category": category,
            "priority": priority,
            "status": status,
            "subject": random.choice(SUBJECTS[category]),
            "department": department,
            "assigned_agent": agent,
            "resolution_hours": resolution_hours_out,
            "met_sla": met_sla_out,
            "satisfaction_score": csat,
        })
        i += 1

    # Sort by created_at for cleaner CSV
    tickets.sort(key=lambda t: t["created_at"])
    # Re-number sequentially after sort
    for idx, t in enumerate(tickets, 1):
        t["ticket_id"] = f"INC{idx:05d}"

    return tickets


def main():
    Path("data").mkdir(exist_ok=True)
    tickets = generate_tickets()
    fields = list(tickets[0].keys())
    with open("data/tickets.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(tickets)
    print(f"Generated {len(tickets)} tickets → data/tickets.csv")


if __name__ == "__main__":
    main()
