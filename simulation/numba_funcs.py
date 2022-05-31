# pylint: disable=missing-docstring, not-an-iterable, invalid-name

import numpy as np

from numba import njit, prange  # type: ignore

from constants import G


@njit()
def norm(vector):

    return np.sqrt(
        vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]
    )


@njit()
def calc_acceleration(
    star_mass,
    planet_mass,
    star_pos,
    planet_pos,
    sat_pos,
    star_accel,
    planet_accel,
    sat_accel,
    r_star_to_sat,
    r_star_to_planet,
    r_planet_to_sat,
):

    # vector from star to satellite

    for j in range(3):
        r_star_to_sat[j] = sat_pos[j] - star_pos[j]

        r_star_to_planet[j] = planet_pos[j] - star_pos[j]

        r_planet_to_sat[j] = sat_pos[j] - planet_pos[j]

    # distance between star to planet
    d_star_to_planet = norm(r_star_to_planet)

    d_star_to_sat = norm(r_star_to_sat)

    d_planet_to_sat = norm(r_planet_to_sat)

    for j in range(3):
        # gravity of satellite can be ignored
        # note the lack of negative sign in the following line
        star_accel[j] = G * planet_mass * r_star_to_planet[j] / d_star_to_planet**3

        planet_accel[j] = -G * star_mass * r_star_to_planet[j] / d_star_to_planet**3

        sat_accel[j] = (
            -G * star_mass * r_star_to_sat[j] / d_star_to_sat**3
            + -G * planet_mass * r_planet_to_sat[j] / d_planet_to_sat**3
        )


@njit()
def integrate(
    time_step,
    num_steps,
    star_mass,
    planet_mass,
    star_pos,
    star_vel,
    planet_pos,
    planet_vel,
    sat_pos,
    sat_vel,
):

    star_accel = np.empty(3, dtype=np.double)

    planet_accel = np.empty_like(star_accel)

    sat_accel = np.empty_like(star_accel)

    star_intermediate_pos = np.empty_like(star_accel)

    planet_intermediate_pos = np.empty_like(star_accel)

    sat_intermediate_pos = np.empty_like(star_accel)

    r_star_to_sat = np.empty_like(star_accel)

    r_star_to_planet = np.empty_like(star_accel)

    r_planet_to_sat = np.empty_like(star_accel)

    for k in range(1, num_steps + 1):

        for j in range(3):

            # intermediate position calculation
            star_intermediate_pos[j] = (
                star_pos[k - 1, j] + 0.5 * star_vel[k - 1, j] * time_step
            )

            planet_intermediate_pos[j] = (
                planet_pos[k - 1, j] + 0.5 * planet_vel[k - 1, j] * time_step
            )

            sat_intermediate_pos[j] = (
                sat_pos[k - 1, j] + 0.5 * sat_vel[k - 1, j] * time_step
            )

        # acceleration calculation
        calc_acceleration(
            star_mass,
            planet_mass,
            star_intermediate_pos,
            planet_intermediate_pos,
            sat_intermediate_pos,
            star_accel,
            planet_accel,
            sat_accel,
            r_star_to_sat,
            r_star_to_planet,
            r_planet_to_sat,
        )

        # velocity update
        star_vel[k] = star_vel[k - 1] + star_accel * time_step

        planet_vel[k] = planet_vel[k - 1] + planet_accel * time_step

        sat_vel[k] = sat_vel[k - 1] + sat_accel * time_step

        # position update
        star_pos[k] = star_intermediate_pos + 0.5 * star_vel[k] * time_step

        planet_pos[k] = planet_intermediate_pos + 0.5 * planet_vel[k] * time_step

        sat_pos[k] = sat_intermediate_pos + 0.5 * sat_vel[k] * time_step


@njit(parallel=True)
def transform_to_corotating(times, angular_speed, pos_trans):
    # it is necessary to transform our coordinate system to one which
    # rotates with the system
    # we can do this by linearly transforming each position vector by
    # the inverse of the coordinate transform
    # the coordinate transform is unit(x) -> R(w*t)*unit(x), unit(y) -> R(w*t)*unit(y)
    # where R(w*t) is the rotation matrix with angle w*t about the z axis
    # the inverse is R(-w*t)
    # at each time t we multiply the position vectors by the matrix R(-w*t)

    # The origin of the coordinate system is the Center of Mass

    pos_rotated = np.empty_like(pos_trans)

    for i in prange(pos_trans.shape[0]):

        t = times[i]

        angle = -angular_speed * t

        cos = np.cos(angle)

        sin = np.sin(angle)

        pos_trans_x = pos_trans[i, 0]

        pos_trans_y = pos_trans[i, 1]

        pos_rotated[i, 0] = cos * pos_trans_x - sin * pos_trans_y

        pos_rotated[i, 1] = sin * pos_trans_x + cos * pos_trans_y

    pos_rotated[:, 2] = 0

    return pos_rotated