from chatbot.models import CandidateFact


def fact_review_action_error(*, action, changed, status, is_public):
    if action != "save" and changed:
        return "Save your text changes before choosing a review decision."
    if action == "save":
        return None
    if action == "approve" and status != CandidateFact.VerificationStatus.PENDING:
        return "Only pending facts can be approved."
    if action == "reject" and status == CandidateFact.VerificationStatus.REJECTED:
        return "This fact has already been rejected."
    if action == "reopen" and status != CandidateFact.VerificationStatus.REJECTED:
        return "Only rejected facts can be reopened."
    if action == "publish" and (
        status != CandidateFact.VerificationStatus.VERIFIED or is_public
    ):
        return "Only verified private facts can be published."
    if action == "unpublish" and not is_public:
        return "Only public facts can be unpublished."
    return None
