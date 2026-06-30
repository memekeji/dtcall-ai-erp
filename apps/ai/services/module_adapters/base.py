class AIBaseModuleAdapter:
    resource = ''

    def supports(self, action):
        return action.resource == self.resource
