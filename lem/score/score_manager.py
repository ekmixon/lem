from lem.score import Score

class ScoreManager(object):
    def __init__(self):
        self.scores = {}

    def add_score(self, name, pattern, example=None):
        if name not in self.scores.keys():
            self.scores[name] = Score(name, pattern, example)

    def delete_score(self, name):
        self.scores.pop(name)

    def get_pattern(self, name):
        return self.scores[name].pattern

    def update_score(self, name, pattern):
        self.scores[name] = Score(name, pattern)

    def is_valid(self, name, value):
        return self.scores[name].is_valid(value)

    def __str__(self):
        score_strings = ['name,pattern,example']
        score_strings.extend(str(score) for _, score in self.scores.iteritems())
        return '\n'.join(score_strings)

    def __iter__(self):
        return iter(self.scores)
