# pylint: disable=invalid-name, missing-docstring
"""Investigating L4 Lagrange Point
using the position Verlet algorithm"""

# to measure time taken in computing. for testing purposes only.
from functools import wraps
from time import perf_counter

# numpy allows us to compute common math functions and work with arrays.
import numpy as np

# plotting module.
import pyqtgraph as pg  # type: ignore
from numpy.linalg import norm
from pyqtgraph.Qt.QtCore import QTimer  # type: ignore

pi = np.pi

# mass of sun in kilograms
sun_mass = 1.98847 * 10**30

# mass of earth in kilograms
earth_mass = 5.9722 * 10**24

# mass of satellite near in kilograms
# negligible compared to other masses
sat_mass = 1.0

# universal gravitational constant in meters^3*1/kilograms*1/seconds^2
G = 6.67430 * 10 ** (-11)

# 1 Julian year in seconds
# serves as a conversion factor from years to seconds
years = 365.25 * 24 * 60 * 60

orbital_period = 1 * years

angular_speed = 2 * pi / orbital_period

# 1 AU in meters
# serves as a conversion factor from AUs to meters
AU = 1.495978707 * 10**11

hill_radius = 1 * AU * (earth_mass / (3 * sun_mass)) ** (1 / 3)

# Position of L1
L1 = 1 * AU * np.array((1, 0, 0)) - np.array((hill_radius, 0, 0))

# Position of L2
L2 = 1 * AU * np.array((1, 0, 0)) + np.array((hill_radius, 0, 0))

L3_dist = 1 * AU * 7 / 12 * earth_mass / sun_mass

# Position of L3
# Located opposite of the Earth and slightly further away from the
L3 = -1 * AU * np.array((1, 0, 0)) - np.array((L3_dist, 0, 0))

# Position of L4 Lagrange point.
# It is 1 AU from both Sun and Earth.
# It forms a 60 degree=pi/3 radians angle with the positive x-axis.
L4 = 1 * AU * np.array((np.cos(pi / 3), np.sin(pi / 3), 0))

# Position of L5 Lagrange point.
# It is 1 AU from both Sun and Earth.
# It forms a 60 degree=pi/3 radians angle with the positive x-axis.
L5 = 1 * AU * np.array((np.cos(pi / 3), -np.sin(pi / 3), 0))

try:
    # cythonized version of integrate_py
    # roughly 270x times faster
    from integrate_cy import integrate  # type: ignore

except ImportError:

    from integrate_py import integrate

try:

    # cythonized version of transform_to_corotating
    # roughly 100x times faster
    from transform_cy import transform_to_corotating  # type: ignore

except ImportError:

    from transform_py import transform_to_corotating


def time_func(func):
    """Measures the time taken by a function"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        print(f"{func.__name__} took {end - start} seconds")
        return result

    return wrapper


@time_func
def main(
    num_years=10.0,
    num_steps=1 * 10**5,
    perturbation_size=0,
    perturbation_angle=None,
    speed=1,
    vel_angle=None,
    default_pos=L4,
    plot_conserved=False,
):
    """main simulates and creates plots of satellite's orbit in inertial and corotating frames

    takes the following parameters:

    num_years: number of years to simulate
    num_steps: number of steps to simulate

    perturbation_size: size of perturbation in AU
    perturbation_angle: angle of perturbation relative to positive x axis in degrees

    speed: initial speed of satellite as a factor of Earth's speed
    i.e. speed = 1 -> satellite has the same speed as Earth
    vel_angle: angle of satellite's initial velocity relative to positive x axis in degrees

    default_pos: non perturbed position of satellite. default is L4 but L1, L2, L3, L5 can be used

    plot_conserved: if True, plots the conserved quantities:
    energy, angular momentum, linear momentum

    integrate: function to use for integration. default is integrate_cy.
    integrate_py is used if integrate_cy is not available.
    """

    # this function will take ~0.15 seconds per 10**5 steps
    # the time may vary depending on your hardware

    default_pertubation_angle = np.arctan2(default_pos[1], default_pos[0])

    default_pertubation_angle = np.degrees(default_pertubation_angle)

    if perturbation_angle is None:

        perturbation_angle = default_pertubation_angle

    if vel_angle is None:

        vel_angle = default_pertubation_angle + 90

    sun_pos, sun_vel, earth_pos, earth_vel, sat_pos, sat_vel = calc_orbit(
        num_years,
        num_steps,
        perturbation_size,
        perturbation_angle,
        speed,
        vel_angle,
        default_pos,
    )

    # position of Center of Mass at each timestep
    CM_pos = calc_center_of_mass(sun_pos, earth_pos, sat_pos)

    plot_orbit(sun_pos, earth_pos, sat_pos)

    # converting num_years to seconds
    time_stop = num_years * years

    # array of num_steps+1 time points evenly spaced between 0 and time_stop
    times = np.linspace(0, time_stop, num_steps + 1)

    sun_pos_trans = transform_to_corotating(times, sun_pos, CM_pos)

    earth_pos_trans = transform_to_corotating(times, earth_pos, CM_pos)

    sat_pos_trans = transform_to_corotating(times, sat_pos, CM_pos)

    plot_corotating_orbit(
        default_pos, sun_pos_trans, earth_pos_trans, sat_pos_trans, num_years
    )

    if plot_conserved:
        (
            total_momentum,
            total_angular_momentum,
            total_energy,
        ) = conservation_calculations(
            sun_pos, sun_vel, earth_pos, earth_vel, sat_pos, sat_vel
        )

        earth_momentum = earth_mass * earth_vel[0]

        plot_conserved_func(
            times, earth_momentum, total_momentum, total_angular_momentum, total_energy
        )


def calc_orbit(
    num_years=10.0,
    num_steps=1 * 10**5,
    perturbation_size=0,
    perturbation_angle=None,
    speed=1,
    vel_angle=None,
    default_pos=L4,
):
    default_pertubation_angle = np.arctan2(default_pos[1], default_pos[0])

    default_pertubation_angle = np.degrees(default_pertubation_angle)

    if perturbation_angle is None:

        perturbation_angle = default_pertubation_angle

    if vel_angle is None:

        vel_angle = default_pertubation_angle + 90

    sun_pos, sun_vel, earth_pos, earth_vel, sat_pos, sat_vel = initialization(
        num_steps, perturbation_size, perturbation_angle, speed, vel_angle, default_pos
    )

    # converting num_years to seconds
    time_stop = num_years * years

    time_step = time_stop / num_steps

    return integrate(
        time_step, num_steps, sun_pos, sun_vel, earth_pos, earth_vel, sat_pos, sat_vel
    )


def initialization(
    num_steps,
    perturbation_size,
    perturbation_angle,
    speed,
    vel_angle,
    default_pos=L4,
):
    """Initializes the arrays of positions and velocities
    so that their initial values correspond to the input parameters
    """

    # creating position and velocity vector arrays

    # array of position vectors for sun
    sun_pos = np.empty((num_steps + 1, 3), dtype=np.double)

    # array of velocity vectors for sun
    sun_vel = np.empty_like(sun_pos)

    # array of position vectors for earth
    earth_pos = np.empty_like(sun_pos)

    # array of velocity vectors for earth
    earth_vel = np.empty_like(sun_pos)

    # array of position vectors for satellite
    sat_pos = np.empty_like(sun_pos)

    # array of velocity vectors for satellite
    sat_vel = np.empty_like(sun_pos)

    # sun is initially at origin but its position is not fixed
    sun_pos[0] = np.array((0, 0, 0))

    # earth starts 1 AU from the sun (and origin) and lies on the positive x-axis
    earth_pos[0] = np.array((1 * AU, 0, 0))

    # Perturbation #

    perturbation_size = perturbation_size * AU

    perturbation_angle = np.radians(perturbation_angle)

    perturbation = perturbation_size * np.array(
        (np.cos(perturbation_angle), np.sin(perturbation_angle), 0)
    )

    # perturbing the initial position of the satellite
    sat_pos[0] = default_pos + perturbation

    # all 3 masses orbit about the Center of Mass at an angular_speed = 1 orbit/year =
    # 2 pi radians/year
    # we setup conditions so that the earth and sun have circular orbits
    # velocities have to be defined relative to the CM
    init_CM_pos = calc_center_of_mass(sun_pos[0], earth_pos[0], sat_pos[0])

    # orbits are counter clockwise so
    # angular velocity is in the positive z direction
    angular_vel = np.array((0, 0, angular_speed))

    speed = speed * norm(np.cross(angular_vel, earth_pos[0] - init_CM_pos))

    vel_angle = np.radians(vel_angle)

    sat_vel[0] = speed * np.array((np.cos(vel_angle), np.sin(vel_angle), 0))

    # End Perturbation #

    # for a circular orbit velocity = cross_product(angular velocity, position)
    # where vec(position) is the position relative to the point being orbited
    # in this case the Center of Mass
    sun_vel[0] = np.cross(angular_vel, sun_pos[0] - init_CM_pos)

    earth_vel[0] = np.cross(angular_vel, earth_pos[0] - init_CM_pos)

    return sun_pos, sun_vel, earth_pos, earth_vel, sat_pos, sat_vel


def calc_center_of_mass(sun_pos, earth_pos, sat_pos):

    return (sun_mass * sun_pos + earth_mass * earth_pos + sat_mass * sat_pos) / (
        sun_mass + earth_mass + sat_mass
    )


timer = QTimer()


def plot_orbit(sun_pos, earth_pos, sat_pos):

    orbit_plot = pg.plot(title="Orbits of Masses")
    orbit_plot.setLabel("bottom", "x", units="AU")
    orbit_plot.setLabel("left", "y", units="AU")
    orbit_plot.addLegend()

    orbit_plot.setXRange(-1.2, 1.2)
    orbit_plot.setYRange(-1.2, 1.2)
    orbit_plot.setAspectLocked(True)

    # zoom into the sun until the axes are on the scale of a few micro-AU to see sun's orbit
    orbit_plot.plot(sun_pos[:, 0] / AU, sun_pos[:, 1] / AU, pen="y", name="Sun")

    orbit_plot.plot(earth_pos[:, 0] / AU, earth_pos[:, 1] / AU, pen="b", name="Earth")

    orbit_plot.plot(sat_pos[:, 0] / AU, sat_pos[:, 1] / AU, pen="g", name="Satellite")

    anim_plot = pg.ScatterPlotItem()

    orbit_plot.addItem(anim_plot)

    idx = update_idx(sun_pos.shape[0])

    def update_plot():

        i = next(idx)

        anim_plot.clear()

        anim_plot.addPoints(
            [sun_pos[i, 0] / AU],
            [sun_pos[i, 1] / AU],
            pen="y",
            brush="y",
            size=10,
            name="Sun",
        )

        anim_plot.addPoints(
            [earth_pos[i, 0] / AU],
            [earth_pos[i, 1] / AU],
            pen="b",
            brush="b",
            size=10,
            name="Earth",
        )

        anim_plot.addPoints(
            [sat_pos[i, 0] / AU],
            [sat_pos[i, 1] / AU],
            pen="g",
            brush="g",
            size=10,
            name="Satellite",
        )

    # time in milliseconds between plot updates
    # making it small (=1) and having 2 animated plots leads to crashes
    period = 33

    timer.timeout.connect(update_plot)
    timer.start(period)


def update_idx(num_steps):
    """This function is used to update the index of the orbit plot"""

    i = 0

    # maximum rate of plot update is too slow
    # so instead step through arrays at a step of rate
    # TODO: replace rate with some function of num_step and time_step
    # so that animation is always at correct speed regardless of num_step or time_step
    rate = 150

    while True:

        i = i + rate

        if i >= num_steps:
            i = 0

        yield i


timer_rotating = QTimer()


def plot_corotating_orbit(
    default_pos, sun_pos_trans, earth_pos_trans, sat_pos_trans, num_years
):

    # Animated plot of satellites orbit in co-rotating frame.
    transform_plot = pg.plot(title="Orbits in Co-Rotating Coordinate System")
    transform_plot.setLabel("bottom", "x", units="AU")
    transform_plot.setLabel("left", "y", units="AU")
    transform_plot.addLegend()

    transform_plot.setXRange(-0.2, 1.2)
    transform_plot.setYRange(-0.2, 1.2)
    transform_plot.setAspectLocked(True)

    anim_trans_plot = pg.ScatterPlotItem()

    transform_plot.addItem(anim_trans_plot)

    transform_plot.plot(
        sat_pos_trans[:, 0] / AU,
        sat_pos_trans[:, 1] / AU,
        name="Satellite orbit",
        pen="g",
    )

    # The only purpose of this is to add the bodies to the plot legend
    transform_plot.plot(
        [sun_pos_trans[0, 0] / AU],
        [sun_pos_trans[0, 1] / AU],
        name="Sun",
        pen="k",
        symbol="o",
        symbolPen="y",
        symbolBrush="y",
    )

    transform_plot.plot(
        [earth_pos_trans[0, 0] / AU],
        [earth_pos_trans[0, 1] / AU],
        name="Earth",
        pen="k",
        symbol="o",
        symbolPen="b",
        symbolBrush="b",
    )

    transform_plot.plot(
        [default_pos[0] / AU],
        [default_pos[1] / AU],
        name="Lagrange Point L4",
        pen="k",
        symbol="o",
        symbolPen="w",
        symbolBrush="w",
    )

    num_steps = sun_pos_trans.shape[0] - 1

    idx = update_idx(num_steps)

    def update_trans():

        j = next(idx)

        anim_trans_plot.clear()

        anim_trans_plot.addPoints(
            [default_pos[0] / AU],
            [default_pos[1] / AU],
            pen="w",
            brush="w",
            size=10,
            name="initial position",
        )

        anim_trans_plot.addPoints(
            [sun_pos_trans[j, 0] / AU],
            [sun_pos_trans[j, 1] / AU],
            pen="y",
            brush="y",
            size=10,
            name="Sun",
        )

        anim_trans_plot.addPoints(
            [earth_pos_trans[j, 0] / AU],
            [earth_pos_trans[j, 1] / AU],
            pen="b",
            brush="b",
            size=10,
            name="Earth",
        )

        anim_trans_plot.addPoints(
            [sat_pos_trans[j, 0] / AU],
            [sat_pos_trans[j, 1] / AU],
            pen="g",
            brush="g",
            size=10,
            name="Satellite",
        )

        # steps_per_year = int(num_steps / num_years)

        # plots where the satellite is after 1 year
        # anim_trans_plot.addPoints(
        #     [sat_pos_trans[steps_per_year, 0] / AU],
        #     [sat_pos_trans[steps_per_year, 1] / AU],
        #     pen="g",
        #     brush="w",
        #     size=10,
        #     name="Satellite 1 yr",
        # )

    # time in milliseconds between plot updates
    # making it small (=1) and having 2 animated plots leads to crashes
    period = 33

    timer_rotating.timeout.connect(update_trans)
    timer_rotating.start(period)


def conservation_calculations(sun_pos, sun_vel, earth_pos, earth_vel, sat_pos, sat_vel):

    total_momentum = sun_mass * sun_vel + earth_mass * earth_vel + sat_mass * sat_vel

    angular_momentum_sun = np.cross(sun_pos, sun_mass * sun_vel)

    angular_momentum_earth = np.cross(earth_pos, earth_mass * earth_vel)

    angular_momentum_sat = np.cross(sat_pos, sat_mass * sat_vel)

    total_angular_momentum = (
        angular_momentum_sun + angular_momentum_earth + angular_momentum_sat
    )

    # array of the distance between earth and sun at each timestep
    d_earth_to_sun = norm(sun_pos - earth_pos, axis=1)

    d_earth_to_sat = norm(sat_pos - earth_pos, axis=1)

    d_sun_to_sat = norm(sat_pos - sun_pos, axis=1)

    potential_energy = (
        -G * sun_mass * earth_mass / d_earth_to_sun
        + -G * sat_mass * earth_mass / d_earth_to_sat
        + -G * sat_mass * sun_mass / d_sun_to_sat
    )

    # array of the magnitude of the velocity of sun at each timestep
    mag_sun_vel = norm(sun_vel, axis=1)

    mag_earth_vel = norm(earth_vel, axis=1)

    mag_sat_vel = norm(sat_vel, axis=1)

    kinetic_energy = (
        0.5 * sun_mass * mag_sun_vel**2
        + 0.5 * earth_mass * mag_earth_vel**2
        + 0.5 * sat_mass * mag_sat_vel**2
    )

    total_energy = potential_energy + kinetic_energy

    return total_momentum, total_angular_momentum, total_energy


def plot_conserved_func(
    times, earth_momentum, total_momentum, total_angular_momentum, total_energy
):
    # sourcery skip: extract-duplicate-method

    times_in_years = times / years

    linear_momentum_plot = pg.plot(title="Normalized Linear Momentum vs Time")
    linear_momentum_plot.setLabel("bottom", "Time", units="years")
    linear_momentum_plot.setLabel("left", "Normalized Linear Momentum")

    linear_momentum_plot.addLegend()

    # total linear momentum is not conserved (likely due to floating point errors)
    # however the variation is insignificant compared to
    # the Sun's and Earth's individual linear momenta
    linear_momentum_plot.plot(
        times_in_years,
        total_momentum[:, 0] / norm(earth_momentum),
        pen="r",
        name="x",
    )

    linear_momentum_plot.plot(
        times_in_years,
        total_momentum[:, 1] / norm(earth_momentum),
        pen="g",
        name="y",
    )

    linear_momentum_plot.plot(
        times_in_years,
        total_momentum[:, 2] / norm(earth_momentum),
        pen="b",
        name="z",
    )

    angular_momentum_plot = pg.plot(title="Normalized Angular Momenta vs Time")
    angular_momentum_plot.setLabel("bottom", "Time", units="years")
    angular_momentum_plot.setLabel("left", "Normalized Angular Momentum")

    angular_momentum_plot.addLegend()

    # x and y components of angular momentum are 0
    # angular_momentum_plot.plot(
    #   times_in_years,
    #   total_angular_momentum[:, 0]/total_angular_momentum[0, 0]-1,
    #   pen='r',
    #   name='x'
    # )

    # angular_momentum_plot.plot(
    #   times_in_years,
    #   total_angular_momentum[:, 1]/total_angular_momentum[0, 1]-1,
    #   pen='g',
    #   name='y'
    # )

    angular_momentum_plot.plot(
        times_in_years,
        total_angular_momentum[:, 2] / total_angular_momentum[0, 2] - 1,
        pen="b",
        name="z",
    )

    energy_plot = pg.plot(title="Normalized Energy vs Time")
    energy_plot.setLabel("bottom", "Time", units="years")
    energy_plot.setLabel("left", "Normalized Energy")

    energy_plot.plot(times_in_years, total_energy / total_energy[0] - 1)


def calc_period_from_initial_conditions(
    perturbation_size, perturbation_angle, speed, vel_angle, default_pos=L4
):

    sat_pos, sat_vel, CM_pos = get_sat_initial_conditions(
        perturbation_size, perturbation_angle, speed, vel_angle, default_pos
    )

    semi_major_axis = calc_semi_major_axis_from_initial_conditions(
        sat_pos, sat_vel, CM_pos
    )

    return calc_period_from_semi_major_axis(semi_major_axis)


def get_sat_initial_conditions(
    perturbation_size, perturbation_angle, speed, vel_angle, default_pos=L4
):

    sun_pos, _, earth_pos, _, sat_pos, sat_vel = initialization(
        0, perturbation_size, perturbation_angle, speed, vel_angle, default_pos
    )

    init_CM_pos = calc_center_of_mass(sun_pos, earth_pos, sat_pos)[0]

    init_sat_pos, init_sat_vel = sat_pos[0], sat_vel[0]

    return init_sat_pos, init_sat_vel, init_CM_pos


def calc_semi_major_axis_from_initial_conditions(sat_pos, sat_vel, CM_pos):

    # Treating the influence of earth on the satellite as negligible
    # Therefore we can apply the solution to the 2-body problem to the satellite

    # See "2 body analytic.docx" and "solve for orbital parameters.docx" for a derivation
    # of the following procedure

    sat_pos = sat_pos - CM_pos

    unit_pos = sat_pos / norm(sat_pos)

    # 90 degrees
    angle = pi / 2

    # rotates by 90 degrees counter-clockwise
    rotation_matrix = np.array(
        (
            (np.cos(angle), -np.sin(angle), 0),
            (np.sin(angle), np.cos(angle), 0),
            (0, 0, 1),
        )
    )

    unit_angular = rotation_matrix.dot(unit_pos)

    radial_vel = np.dot(sat_vel, unit_pos)

    transverse_vel = np.dot(sat_vel, unit_angular)

    angular_momentum = np.cross(sat_pos, sat_mass * sat_vel)

    angular_momentum = norm(angular_momentum)

    gravitational_coefficient = G * sun_mass * sat_mass

    transverse_vel_prime = -(
        transverse_vel - gravitational_coefficient / angular_momentum
    )

    eccentricity_squared = (
        -angular_momentum / gravitational_coefficient * radial_vel
    ) ** 2 + (angular_momentum / gravitational_coefficient * transverse_vel_prime) ** 2

    reduced_mass = sun_mass * sat_mass / (sun_mass + sat_mass)

    return angular_momentum**2 / (
        gravitational_coefficient * reduced_mass * (1 - eccentricity_squared)
    )


def calc_period_from_semi_major_axis(semi_major_axis):

    period_squared = 4 * pi**2 * semi_major_axis**3 / (G * sun_mass)

    return np.sqrt(period_squared)


def calc_period_from_position_data(sat_pos, CM_pos):

    semi_major_axis = calc_semi_major_axis_from_position_data(sat_pos, CM_pos)

    return calc_period_from_semi_major_axis(semi_major_axis)


def calc_semi_major_axis_from_position_data(sat_pos, CM_pos):

    sat_pos = sat_pos - CM_pos

    distances = norm(sat_pos, axis=1)

    perihelion = min(distances)

    aphelion = max(distances)

    return (perihelion + aphelion) / 2