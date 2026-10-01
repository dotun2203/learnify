from .models import Academy, AcademyMembership


def academies_for_user(user):
    return (
        Academy.objects.filter(memberships__user=user)
        .exclude(status=Academy.Status.SUSPENDED)
        .prefetch_related("memberships")
        .distinct()
    )


def memberships_for_user(user):
    """Active academies the user can manage, with their role in each."""
    return (
        AcademyMembership.objects.filter(user=user)
        .exclude(academy__status=Academy.Status.SUSPENDED)
        .select_related("academy")
        .order_by("academy__name")
    )


def onboarding_checklist(academy):
    """What the Studio wizard renders. Each step: key, label, done, blocking.

    Blocking steps must all be done before the academy can go active
    (and therefore before any course can be published).
    """
    steps = [
        {
            "key": "profile",
            "label": "Add your academy name, tagline and description",
            "done": bool(academy.name and academy.tagline and academy.description),
            "blocking": True,
        },
        {
            "key": "branding",
            "label": "Upload a logo",
            "done": bool(academy.logo),
            "blocking": True,
        },
        {
            "key": "contact",
            "label": "Add a support email or WhatsApp number",
            "done": bool(academy.support_email or academy.whatsapp_number),
            "blocking": True,
        },
        {
            "key": "payouts",
            "label": "Connect your bank account to receive payments",
            "done": bool(academy.paystack_subaccount_code),
            "blocking": False,  # becomes blocking when payments ship
        },
    ]
    blocking_done = all(s["done"] for s in steps if s["blocking"])
    return {
        "status": academy.status,
        "can_activate": blocking_done and not academy.is_active,
        "complete": blocking_done,
        "steps": steps,
    }


def slug_is_available(slug):
    return not Academy.objects.filter(slug=slug).exists()