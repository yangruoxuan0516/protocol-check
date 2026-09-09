def select_requirement_nios(nios, check_all_nios=False):
    return [
        nio
        for nio in nios
        if nio.type == "requirement"
        and (check_all_nios or nio.req == "Yes")
    ]
