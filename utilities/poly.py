#
# Polynomial calculator
# (Yes I know I could use numpy but don't want the overhead)
#
class Poly():
    def __init__(self, coeffs):
        self.coeffs = coeffs
        self.ncoeffs = len(coeffs)

    def calc(self, x):
        y = self.coeffs[self.ncoeffs - 1]

        for coeff in range(self.ncoeffs - 2, -1, -1):
            y = y * x + self.coeffs[coeff]

        return y


