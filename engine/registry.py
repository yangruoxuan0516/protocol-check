from checks.cor_02_01.single_shall import (
    SingleShallCheck,
)
from checks.cor_02_01.factual_correct import (
    FactualCorrectCheck,
)


CHECKS = {
    "COR-02.01.single_shall":
        SingleShallCheck(),

    "COR-02.01.factual_correct":
        FactualCorrectCheck(),
}


def get_check(check_id: str):
    try:
        return CHECKS[check_id]
    except KeyError:
        available = "\n".join(
            sorted(CHECKS.keys())
        )

        raise KeyError(
            f"Unknown check: {check_id}\n\n"
            f"Available checks:\n{available}"
        )


def get_checks_by_prefix(prefix: str):
    return [
        check
        for check_id, check in CHECKS.items()
        if check_id.startswith(prefix)
    ]