# -*- coding: utf-8 -*-
# GRID is a numerical integration module for quantum chemistry.
#
# Copyright (C) 2011-2019 The GRID Development Team
#
# This file is part of GRID.
#
# GRID is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# GRID is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
# --
"""ODE test module."""
from numbers import Number
from unittest import TestCase

from grid.ode import ODE
from grid.onedgrid import GaussLaguerre
from grid.rtransform import (
    BaseTransform,
    BeckeRTransform,
    IdentityRTransform,
    InverseRTransform,
    LinearFiniteRTransform,
)

import numpy as np
from numpy.testing import assert_allclose, assert_almost_equal

from scipy.integrate import solve_bvp


class TestODE(TestCase):
    """ODE solver test class."""

    def test_transform_coeff_with_x_and_r(self):
        """Test coefficient transform between x and r."""
        coeff = np.array([2, 3, 4])
        ltf = LinearFiniteRTransform(1, 10)  # (-1, 1) -> (r0, rmax)
        inv_tf = InverseRTransform(ltf)  # (r0, rmax) -> (-1, 1)
        x = np.linspace(-1, 1, 20)
        r = ltf.transform(x)
        assert r[0] == 1
        assert r[-1] == 10
        # Transform ODE from [1, 10) to (-1, 1)
        coeff_transform = ODE._transform_ode_from_rtransform(coeff, inv_tf, x)
        derivs_fun = [inv_tf.deriv, inv_tf.deriv2, inv_tf.deriv3]
        coeff_transform_all_pts = ODE._transform_ode_from_derivs(coeff, derivs_fun, r)
        assert_allclose(coeff_transform, coeff_transform_all_pts)

    def test_transformation_of_ode_with_identity_transform(self):
        """Test transformation of ODE with identity transform."""
        # Checks that the identity transform x -> x results in the same answer.
        # Obtain identity trasnform and derivatives.
        itf = IdentityRTransform()
        inv_tf = InverseRTransform(itf)
        derivs_fun = [inv_tf.deriv, inv_tf.deriv2, inv_tf.deriv3]
        # d^2y / dx^2 = 1
        coeff = np.array([0, 0, 1])
        x = np.linspace(0, 1, 10)
        # compute transformed coeffs
        coeff_b = ODE._transform_ode_from_derivs(coeff, derivs_fun, x)
        # f_x = 0 * x + 1  # 1 for every
        assert_allclose(coeff_b, np.zeros((3, 10), dtype=float) + coeff[:, None])

    def test_transformation_of_ode_with_linear_transform(self):
        """Test transformation of ODE with linear transformation."""
        x = GaussLaguerre(10).points
        # Obtain linear transformation with rmin = 1 and rmax = 10.
        ltf = LinearFiniteRTransform(1, 10)
        # The inverse is x_i = \frac{r_i - r_{min} - R} {r_i - r_{min} + R}
        inv_ltf = InverseRTransform(ltf)
        derivs_fun = [inv_ltf.deriv, inv_ltf.deriv2, inv_ltf.deriv3]
        # Test with 2y + 3y` + 4y``
        coeff = np.array([2, 3, 4])
        coeff_b = ODE._transform_ode_from_derivs(coeff, derivs_fun, x)
        # assert values
        assert_allclose(coeff_b[0], np.ones(len(x)) * coeff[0])
        assert_allclose(coeff_b[1], 1 / 4.5 * coeff[1])
        assert_allclose(coeff_b[2], (1 / 4.5) ** 2 * coeff[2])

    def test_high_order_transformations_gives_itself(self):
        r"""Test transforming then transforming back gives back the same result."""
        # Consider the following transformation x^4 and its derivatives
        def transf(x):
            return x**4.0

        derivs = [
            lambda x: 4.0 * x**3.0,
            lambda x: 4.0 * 3.0 * x**2.0,
            lambda x: 4.0 * 3.0 * 2.0 * x,
            lambda x: 4.0 * 3.0 * 2.0 * np.array([1.0] * len(x)),
        ]

        # Consider ODE 2y + 3y` + 4y`` + 5y``` + 6dy^4/dx^4 and transform it
        coeffs = np.array([2, 3, 4, 5, 6])
        x = np.arange(1.0, 2.0, 0.01)
        coeffs_transf = ODE._transform_ode_from_derivs(coeffs, derivs, x)
        # Transform it back using the derivative of the inverse transformation x^4
        derivs_invs = [
            lambda r: 1.0 / (4.0 * r ** (3.0 / 4.0)),
            lambda r: -3.0 / (16.0 * r ** (7.0 / 4.0)),
            lambda r: 21.0 / (64.0 * r ** (11.0 / 4.0)),
            lambda r: -231.0 / (256.0 * r ** (15.0 / 4.0)),
        ]
        x_transformed = transf(x)
        # Go Through Each Points and grab the new coefficients and transform it back
        for i in range(0, len(x)):
            coeffs_original = ODE._transform_ode_from_derivs(
                np.ravel(coeffs_transf[:, i]), derivs_invs, x_transformed[i : i + 1]
            )
            # Check that it is the same as hte original transformation.
            assert_almost_equal(coeffs, np.ravel(coeffs_original))

    def test_rearange_ode_coeff(self):
        """Test rearange ode coeff and solver result."""
        coeff_b = [0, 0, 1]
        x = np.linspace(0, 2, 20)
        y = np.zeros((2, x.size))  # Initial Guess

        def fx(x):
            return 1 if isinstance(x, Number) else np.ones(x.size)

        def func(x, y):
            dy_dx = ODE._rearrange_to_explicit_ode(y, coeff_b, fx(x))
            return np.vstack((*y[1:], dy_dx))

        def bc(ya, yb):
            # Boundary conditions: zero at endpoints of y
            return np.array([ya[0], yb[0]])

        res = solve_bvp(func, bc, x, y)
        # res = 0.5 * x**2 - x
        assert_almost_equal(res.sol(0)[0], 0)
        assert_almost_equal(res.sol(1)[0], -0.5)
        assert_almost_equal(res.sol(2)[0], 0)
        assert_almost_equal(res.sol(0)[1], -1)
        assert_almost_equal(res.sol(1)[1], 0)
        assert_almost_equal(res.sol(2)[1], 1)

        # 2nd example
        coeff_b_2 = [-3, 2, 1]

        def fx2(x):
            return -6 * x**2 - x + 10

        def func2(x, y):
            dy_dx = ODE._rearrange_to_explicit_ode(y, coeff_b_2, fx2(x))
            return np.vstack((*y[1:], dy_dx))

        def bc2(ya, yb):
            return np.array([ya[0], yb[0] - 14])

        res2 = solve_bvp(func2, bc2, x, y)
        # res2 = 2 * x**2 + 3x
        assert_almost_equal(res2.sol(0)[0], 0)
        assert_almost_equal(res2.sol(1)[0], 5)
        assert_almost_equal(res2.sol(2)[0], 14)
        assert_almost_equal(res2.sol(0)[1], 3)
        assert_almost_equal(res2.sol(1)[1], 7)
        assert_almost_equal(res2.sol(2)[1], 11)

    def test_second_order_ode_with_transformation(self):
        """Test transforming and re-arranging ODE is equivalent without transforming."""
        stf = SqTF()
        coeff = np.array([0, 0, 1])
        # transform
        r = np.linspace(1, 2, 10)  # r
        y = np.zeros((2, r.size))
        x = stf.transform(r)  # transformed x
        assert_almost_equal(x, r**2)

        def fx(x):
            return 1 if isinstance(x, Number) else np.ones(x.size)

        # Run with transformation
        def func(x, y):
            dy_dx = ODE._transform_and_rearrange_to_explicit_ode(x, y, coeff, stf, fx)
            return np.vstack((*y[1:], dy_dx))

        def bc(ya, yb):
            # Boundary of y is zero on endpoints
            return np.array([ya[0], yb[0]])

        res = solve_bvp(func, bc, x, y)

        # Run without transformation
        ref_y = np.zeros((2, r.size))  # Initial Guess

        def func_ref(x, y):
            return np.vstack((y[1:], np.ones(y[0].size)))

        # Run without transformation
        res_ref = solve_bvp(func_ref, bc, r, ref_y)
        # Check if they're equal
        assert_allclose(res.sol(x)[0], res_ref.sol(r)[0], atol=1e-4)

    def test_second_order_ode_with_diff_coeff(self):
        """Test transforming and re-arranging ODE with non-constant function."""
        stf = SqTF()
        stf = SqTF(3, 1)
        coeff = np.array([2, 3, 2])
        # transform
        r = np.linspace(1, 2, 10)  # r
        y = np.zeros((2, r.size))
        x = stf.transform(r)  # transformed x

        def fx(x):
            return 1 / x**3 + 3 * x**2 + x

        def func(x, y):
            dy_dx = ODE._transform_and_rearrange_to_explicit_ode(x, y, coeff, stf, fx)
            return np.vstack((*y[1:], dy_dx))

        def bc(ya, yb):
            return np.array([ya[0], yb[0]])

        res = solve_bvp(func, bc, x, y)
        ref_y = np.zeros((2, r.size))

        def func_ref(x, y):
            return np.vstack((y[1], (fx(x) - 2 * y[0] - 3 * y[1]) / 2))

        res_ref = solve_bvp(func_ref, bc, r, ref_y)
        assert_allclose(res.sol(x)[0], res_ref.sol(r)[0], atol=1e-4)

    def test_second_order_ode_with_fx(self):
        """Test ODE with and without transformation with a non-constant term."""
        stf = SqTF()
        # Test ode 2y + 2y` + 3y``
        coeff = np.array([2, 2, 3])
        # transform
        r = np.linspace(1, 2, 10)  # r
        initial_guess = np.zeros((2, r.size))
        x = stf.transform(r)  # transformed x
        assert_almost_equal(x, r**2)

        # Non-constant term.
        def fx(x):
            return x**2 + 3 * x - 5

        def func(x, y):
            dy_dx = ODE._transform_and_rearrange_to_explicit_ode(x, y, coeff, stf, fx)
            return np.vstack((*y[1:], dy_dx))

        def bc(ya, yb):
            return np.array([ya[0], yb[0]])

        res = solve_bvp(func, bc, x, initial_guess)

        def func_ref(x, y):
            dy_dx = ODE._rearrange_to_explicit_ode(y, coeff, fx(x))
            return np.vstack((*y[1:], dy_dx))

        res_ref = solve_bvp(func_ref, bc, r, initial_guess)
        # Test initial gfunctions are similar
        assert_allclose(res.sol(x)[0], res_ref.sol(r)[0], atol=1e-4)
        # Test first derivatives are similar
        assert_allclose(res.sol(x)[1], res_ref.sol(r)[1] / stf.deriv(r), atol=1e-4)

    def test_becke_transform_2nd_order_ode(self):
        """Test same result for 2nd order ode with becke tf."""
        btf = BeckeRTransform(0.1, 2)
        ibtf = InverseRTransform(btf)
        coeff = np.array([0, 1, 1])
        # transform
        # r = np.linspace(1, 2, 10)  # r
        # x = ibtf.transform(r)  # transformed x
        x = np.linspace(-0.9, 0.9, 20)
        r = ibtf.inverse(x)
        y = np.zeros((2, r.size))

        def fx(x):
            return 1 / x**2

        def func(x, y):
            dy_dx = ODE._transform_and_rearrange_to_explicit_ode(x, y, coeff, ibtf, fx)
            return np.vstack((*y[1:], dy_dx))

        def bc(ya, yb):
            return np.array([ya[0], yb[0]])

        res = solve_bvp(func, bc, x, y)

        def func_ref(x, y):
            dy_dx = ODE._rearrange_to_explicit_ode(y, coeff, fx(x))
            return np.vstack((*y[1:], dy_dx))

        res_ref = solve_bvp(func_ref, bc, r, y)
        print(res_ref.sol(r)[0])

        assert_allclose(res.sol(x)[0], res_ref.sol(r)[0], atol=5e-3)

    def test_becke_transform_3nd_order_ode(self):
        """Test third order ode with Becke transformation against without transformation."""
        btf = BeckeRTransform(0.1, 10)
        ibtf = InverseRTransform(btf)
        # Consider ODE 2y^` + 3y^`` + 3 * dy^3/dx^3 = 1/x^4
        coeff = np.array([0, 2, 3, 3])
        # transform
        x = np.linspace(-0.9, 0.9, 20)
        r = btf.transform(x)
        initial_guess = np.random.rand(3, r.size)

        def fx(x):
            return 1 / x**4

        def func(x, y):
            dy_dx = ODE._transform_and_rearrange_to_explicit_ode(x, y, coeff, ibtf, fx)
            return np.vstack((*y[1:], dy_dx))

        def bc(ya, yb):
            return np.array([ya[0], yb[0], ya[1]])

        res = solve_bvp(func, bc, x, initial_guess, tol=1e-12)

        def func_ref(x, y):
            dy_dx = ODE._rearrange_to_explicit_ode(y, coeff, fx(x))
            return np.vstack((*y[1:], dy_dx))

        res_ref = solve_bvp(func_ref, bc, r, initial_guess, tol=1e-12)
        # Test the original, derivative and second order derivative give the same solution.
        assert_allclose(res.sol(x)[0], res_ref.sol(r)[0], atol=1e-6)
        assert_allclose(0.0, res_ref.sol(r)[1][0])  # Test upper-bound.
        assert_allclose(res.sol(x)[1], res_ref.sol(r)[1] * btf.deriv(x), atol=1e-6)
        assert_allclose(
            res.sol(x)[2],
            res_ref.sol(r)[2] / ibtf.deriv(r) ** 2.0
            + res_ref.sol(r)[1] * -ibtf.deriv2(r) / ibtf.deriv(r) ** 3.0,
            atol=1e-6,
        )

    def test_becke_transform_f0_ode(self):
<<<<<<< HEAD
        """Test same result for 3rd order ode with becke tf and fx term."""
        btf = BeckeRTransform(0.1, 10)
        x = np.linspace(-0.9, 0.9, 20)
        btf = BeckeRTransform(0.1, 5)
        ibtf = InverseRTransform(btf)
=======
        """Test second order ode with (without) Becke transformation and non-constant term."""
        x = np.linspace(-0.9, 0.9, 10)
        btf = BeckeTF(0.1, 5)
        ibtf = InverseTF(btf)
>>>>>>> Change test names and add documentation in ode
        r = btf.transform(x)
        initial_guess = np.random.rand(2, x.size)
        # ODE is -y - y` + 2y`` = -1/x^2
        coeff = [-1, -1, 2]

        def fx(x):
            return -1 / x**2

        def func(x, y):
            dy_dx = ODE._transform_and_rearrange_to_explicit_ode(x, y, coeff, ibtf, fx)
            return np.vstack((*y[1:], dy_dx))

        def bc(ya, yb):
            return np.array([ya[0], yb[0]])

        res = solve_bvp(
            func, bc, x, initial_guess, tol=1e-12, bc_tol=1e-12, max_nodes=10000
        )

        def func_ref(x, y):
            dy_dx = ODE._rearrange_to_explicit_ode(y, coeff, fx(x))
            return np.vstack((*y[1:], dy_dx))

        res_ref = solve_bvp(
            func_ref, bc, r, res.sol(x), tol=1e-12, bc_tol=1e-12, max_nodes=10000
        )
        # Test the original, derivative give the same solution and boundary condition.
        assert_allclose(res.sol(x)[0], res_ref.sol(r)[0], atol=1e-6)
        assert_allclose(
            res.sol(x)[0][0], 0.0, atol=1e-6
        )  # Test lower boundary condition
        assert_allclose(
            res.sol(x)[0][-1], 0.0, atol=1e-6
        )  # Test upper boundary condition
        assert_allclose(res.sol(x)[1], res_ref.sol(r)[1] / ibtf.deriv(r), atol=1e-6)

    def test_solve_ode_bvp_against_analytic_example(self):
        """Test solve_ode against analytic solution."""
        x = np.linspace(0, 2, 10)

        def fx(x):
            return 1 if isinstance(x, Number) else np.ones(x.size)

        # test ode  y^`` = 1
        coeffs = [0, 0, 1]
        # lower and upper bound of y is equal to zero.
        bd_cond = [[0, 0, 0], [1, 0, 0]]

        res = ODE.solve_ode(x, fx, coeffs, bd_cond)

        def solution(x):
            return x**2.0 / 2.0 - x

        def deriv(x):
            return x - 1.0

        rand_pts = np.random.uniform(0.0, 2.0, size=10)
        assert_almost_equal(res(rand_pts)[0], solution(rand_pts))
        assert_almost_equal(res(rand_pts)[1], deriv(rand_pts))

    def test_solver_ode_bvp_with_tf(self):
        """Test solve_ode with transformation and without transformation."""
        x = np.linspace(-0.999, 0.999, 20)
        btf = BeckeRTransform(0.1, 5)
        r = btf.transform(x)
        ibtf = InverseRTransform(btf)

        def fx(x):
            return 1 / x**2

        # Test with ode -y + y` + y``=1/x^2
        coeffs = [-1, 1, 1]
        bd_cond = [(0, 0, 3), (1, 0, 3)]  # Test y(a) = y(b) = 3
        # calculate diff equation wt/w tf.
        res = ODE.solve_ode(x, fx, coeffs, bd_cond, ibtf, tol=1e-7, max_nodes=20000)
        res_ref = ODE.solve_ode(
            r, fx, coeffs, bd_cond, tol=1e-7, max_nodes=20000, initial_guess_y=res(x)
        )
        assert_allclose(res(x)[0], res_ref(r)[0], atol=1e-5)
        assert_allclose(res(x)[0][0], 3.0, atol=1e-5)  # Test lower boundary condition
        assert_allclose(res(x)[0][-1], 3.0, atol=1e-5)  # Test upper boundary condition
        assert_allclose(res(x)[1], res_ref(r)[1] / ibtf.deriv(r), atol=1e-4)

    def test_solver_ode_coeff_a_f_x_with_tf(self):
        """Test ode with a(x) and f(x) involved."""
        x = np.linspace(-0.999, 0.999, 20)
        btf = BeckeRTransform(0.1, 5)
        r = btf.transform(x)
        ibtf = InverseRTransform(btf)

        def fx(x):
            return 0 * x

        coeffs = [lambda x: x**2, lambda x: 1 / x**2, 0.5]
        bd_cond = [(0, 1, 0.0), (1, 1, 0.0)]
        # calculate diff equation wt/w tf.
        res = ODE.solve_ode(x, fx, coeffs, bd_cond, ibtf, tol=1e-7, max_nodes=20000)
        res_ref = ODE.solve_ode(r, fx, coeffs, bd_cond)
        assert_allclose(res(x)[0], res_ref(r)[0], atol=1e-4)
        assert_allclose(res(x)[1][0], 0.0, atol=1e-5)  # Test lower boundary condition
        assert_allclose(res(x)[1][-1], 0.0, atol=1e-5)  # Test upper boundary condition
        assert_allclose(res(x)[1], res_ref(r)[1] / ibtf.deriv(r), atol=1e-4)

    def test_construct_coeffs_of_ode_over_mesh(self):
        """Test construct coefficients over a mesh."""
        # first test
        x = np.linspace(-0.9, 0.9, 20)
        coeff = [2, 1.5, lambda x: x**2]
        coeff_a = ODE._evaluate_coeffs_on_points(x, coeff)
        assert_allclose(coeff_a[0], np.ones(20) * 2)
        assert_allclose(coeff_a[1], np.ones(20) * 1.5)
        assert_allclose(coeff_a[2], x**2)
        # second test
        coeff = [lambda x: 1 / x, 2, lambda x: x**3, lambda x: np.exp(x)]
        coeff_a = ODE._evaluate_coeffs_on_points(x, coeff)
        assert_allclose(coeff_a[0], 1 / x)
        assert_allclose(coeff_a[1], np.ones(20) * 2)
        assert_allclose(coeff_a[2], x**3)
        assert_allclose(coeff_a[3], np.exp(x))

    def test_error_raises(self):
        """Test proper error raises."""
        x = np.linspace(-0.999, 0.999, 20)
        # r = btf.transform(x)

        def fx(x):
            return 1 / x**2

        coeffs = [-1, -2, 1]
        bd_cond = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
        with self.assertRaises(NotImplementedError):
            ODE.solve_ode(x, fx, coeffs, bd_cond[3:])
        with self.assertRaises(NotImplementedError):
            ODE.solve_ode(x, fx, coeffs, bd_cond)
        with self.assertRaises(NotImplementedError):
            test_coeff = [1, 2, 3, 4, 5]
            ODE.solve_ode(x, fx, test_coeff, bd_cond)
        with self.assertRaises(ValueError):
            test_coeff = [1, 2, 3, 3]
            tf = BeckeRTransform(0.1, 1)

            def fx(x):
                return x

            ODE.solve_ode(x, fx, test_coeff, bd_cond[:3], tf)


class SqTF(BaseTransform):
    """Test power transformation class."""

    def __init__(self, exp=2, extra=0):
        """Initialize power transform instance."""
        self._exp = exp
        self._extra = extra

    def transform(self, x):
        """Transform given array."""
        return x**self._exp + self._extra

    def inverse(self, r):
        """Inverse transformed array."""
        return (r - self._extra) ** (1 / self._exp)

    def deriv(self, x):
        """Compute 1st order deriv of TF."""
        return self._exp * x ** (self._exp - 1)

    def deriv2(self, x):
        """Compute 2nd order deriv of TF."""
        return (self._exp - 1) * (self._exp) * x ** (self._exp - 2)

    def deriv3(self, x):
        """Compute 3rd order deriv of TF."""
        return (self._exp - 2) * (self._exp - 1) * (self._exp) * x ** (self._exp - 3)
