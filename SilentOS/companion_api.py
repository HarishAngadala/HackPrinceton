"""Local HTTP client for the optional Deep Agent companion worker."""
from silentos_api import SilentOSClient


class CompanionAPIClient(SilentOSClient):
    def claim(self):
        return self.request('/api/companion/next',{})['command']

    def report(self, command_id, token, outcome, detail):
        return self.request('/api/companion/result',{
            'id':command_id,'claim_token':token,'outcome':outcome,'detail':detail})

    def recent(self):
        return self.request('/api/commands')['commands']
