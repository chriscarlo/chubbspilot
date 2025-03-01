#include "car.h"

namespace {
#define DIM 9
#define EDIM 9
#define MEDIM 9
typedef void (*Hfun)(double *, double *, double *);

double mass;

void set_mass(double x){ mass = x;}

double rotational_inertia;

void set_rotational_inertia(double x){ rotational_inertia = x;}

double center_to_front;

void set_center_to_front(double x){ center_to_front = x;}

double center_to_rear;

void set_center_to_rear(double x){ center_to_rear = x;}

double stiffness_front;

void set_stiffness_front(double x){ stiffness_front = x;}

double stiffness_rear;

void set_stiffness_rear(double x){ stiffness_rear = x;}
const static double MAHA_THRESH_25 = 3.8414588206941227;
const static double MAHA_THRESH_24 = 5.991464547107981;
const static double MAHA_THRESH_30 = 3.8414588206941227;
const static double MAHA_THRESH_26 = 3.8414588206941227;
const static double MAHA_THRESH_27 = 3.8414588206941227;
const static double MAHA_THRESH_29 = 3.8414588206941227;
const static double MAHA_THRESH_28 = 3.8414588206941227;
const static double MAHA_THRESH_31 = 3.8414588206941227;

/******************************************************************************
 *                       Code generated with SymPy 1.12                       *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_7013090005465437157) {
   out_7013090005465437157[0] = delta_x[0] + nom_x[0];
   out_7013090005465437157[1] = delta_x[1] + nom_x[1];
   out_7013090005465437157[2] = delta_x[2] + nom_x[2];
   out_7013090005465437157[3] = delta_x[3] + nom_x[3];
   out_7013090005465437157[4] = delta_x[4] + nom_x[4];
   out_7013090005465437157[5] = delta_x[5] + nom_x[5];
   out_7013090005465437157[6] = delta_x[6] + nom_x[6];
   out_7013090005465437157[7] = delta_x[7] + nom_x[7];
   out_7013090005465437157[8] = delta_x[8] + nom_x[8];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_7341665202261006375) {
   out_7341665202261006375[0] = -nom_x[0] + true_x[0];
   out_7341665202261006375[1] = -nom_x[1] + true_x[1];
   out_7341665202261006375[2] = -nom_x[2] + true_x[2];
   out_7341665202261006375[3] = -nom_x[3] + true_x[3];
   out_7341665202261006375[4] = -nom_x[4] + true_x[4];
   out_7341665202261006375[5] = -nom_x[5] + true_x[5];
   out_7341665202261006375[6] = -nom_x[6] + true_x[6];
   out_7341665202261006375[7] = -nom_x[7] + true_x[7];
   out_7341665202261006375[8] = -nom_x[8] + true_x[8];
}
void H_mod_fun(double *state, double *out_1371433892673034290) {
   out_1371433892673034290[0] = 1.0;
   out_1371433892673034290[1] = 0;
   out_1371433892673034290[2] = 0;
   out_1371433892673034290[3] = 0;
   out_1371433892673034290[4] = 0;
   out_1371433892673034290[5] = 0;
   out_1371433892673034290[6] = 0;
   out_1371433892673034290[7] = 0;
   out_1371433892673034290[8] = 0;
   out_1371433892673034290[9] = 0;
   out_1371433892673034290[10] = 1.0;
   out_1371433892673034290[11] = 0;
   out_1371433892673034290[12] = 0;
   out_1371433892673034290[13] = 0;
   out_1371433892673034290[14] = 0;
   out_1371433892673034290[15] = 0;
   out_1371433892673034290[16] = 0;
   out_1371433892673034290[17] = 0;
   out_1371433892673034290[18] = 0;
   out_1371433892673034290[19] = 0;
   out_1371433892673034290[20] = 1.0;
   out_1371433892673034290[21] = 0;
   out_1371433892673034290[22] = 0;
   out_1371433892673034290[23] = 0;
   out_1371433892673034290[24] = 0;
   out_1371433892673034290[25] = 0;
   out_1371433892673034290[26] = 0;
   out_1371433892673034290[27] = 0;
   out_1371433892673034290[28] = 0;
   out_1371433892673034290[29] = 0;
   out_1371433892673034290[30] = 1.0;
   out_1371433892673034290[31] = 0;
   out_1371433892673034290[32] = 0;
   out_1371433892673034290[33] = 0;
   out_1371433892673034290[34] = 0;
   out_1371433892673034290[35] = 0;
   out_1371433892673034290[36] = 0;
   out_1371433892673034290[37] = 0;
   out_1371433892673034290[38] = 0;
   out_1371433892673034290[39] = 0;
   out_1371433892673034290[40] = 1.0;
   out_1371433892673034290[41] = 0;
   out_1371433892673034290[42] = 0;
   out_1371433892673034290[43] = 0;
   out_1371433892673034290[44] = 0;
   out_1371433892673034290[45] = 0;
   out_1371433892673034290[46] = 0;
   out_1371433892673034290[47] = 0;
   out_1371433892673034290[48] = 0;
   out_1371433892673034290[49] = 0;
   out_1371433892673034290[50] = 1.0;
   out_1371433892673034290[51] = 0;
   out_1371433892673034290[52] = 0;
   out_1371433892673034290[53] = 0;
   out_1371433892673034290[54] = 0;
   out_1371433892673034290[55] = 0;
   out_1371433892673034290[56] = 0;
   out_1371433892673034290[57] = 0;
   out_1371433892673034290[58] = 0;
   out_1371433892673034290[59] = 0;
   out_1371433892673034290[60] = 1.0;
   out_1371433892673034290[61] = 0;
   out_1371433892673034290[62] = 0;
   out_1371433892673034290[63] = 0;
   out_1371433892673034290[64] = 0;
   out_1371433892673034290[65] = 0;
   out_1371433892673034290[66] = 0;
   out_1371433892673034290[67] = 0;
   out_1371433892673034290[68] = 0;
   out_1371433892673034290[69] = 0;
   out_1371433892673034290[70] = 1.0;
   out_1371433892673034290[71] = 0;
   out_1371433892673034290[72] = 0;
   out_1371433892673034290[73] = 0;
   out_1371433892673034290[74] = 0;
   out_1371433892673034290[75] = 0;
   out_1371433892673034290[76] = 0;
   out_1371433892673034290[77] = 0;
   out_1371433892673034290[78] = 0;
   out_1371433892673034290[79] = 0;
   out_1371433892673034290[80] = 1.0;
}
void f_fun(double *state, double dt, double *out_3433941462029035336) {
   out_3433941462029035336[0] = state[0];
   out_3433941462029035336[1] = state[1];
   out_3433941462029035336[2] = state[2];
   out_3433941462029035336[3] = state[3];
   out_3433941462029035336[4] = state[4];
   out_3433941462029035336[5] = dt*((-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]))*state[6] - 9.8000000000000007*state[8] + stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*state[1]) + (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*state[4])) + state[5];
   out_3433941462029035336[6] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*state[4])) + state[6];
   out_3433941462029035336[7] = state[7];
   out_3433941462029035336[8] = state[8];
}
void F_fun(double *state, double dt, double *out_2289925118654541475) {
   out_2289925118654541475[0] = 1;
   out_2289925118654541475[1] = 0;
   out_2289925118654541475[2] = 0;
   out_2289925118654541475[3] = 0;
   out_2289925118654541475[4] = 0;
   out_2289925118654541475[5] = 0;
   out_2289925118654541475[6] = 0;
   out_2289925118654541475[7] = 0;
   out_2289925118654541475[8] = 0;
   out_2289925118654541475[9] = 0;
   out_2289925118654541475[10] = 1;
   out_2289925118654541475[11] = 0;
   out_2289925118654541475[12] = 0;
   out_2289925118654541475[13] = 0;
   out_2289925118654541475[14] = 0;
   out_2289925118654541475[15] = 0;
   out_2289925118654541475[16] = 0;
   out_2289925118654541475[17] = 0;
   out_2289925118654541475[18] = 0;
   out_2289925118654541475[19] = 0;
   out_2289925118654541475[20] = 1;
   out_2289925118654541475[21] = 0;
   out_2289925118654541475[22] = 0;
   out_2289925118654541475[23] = 0;
   out_2289925118654541475[24] = 0;
   out_2289925118654541475[25] = 0;
   out_2289925118654541475[26] = 0;
   out_2289925118654541475[27] = 0;
   out_2289925118654541475[28] = 0;
   out_2289925118654541475[29] = 0;
   out_2289925118654541475[30] = 1;
   out_2289925118654541475[31] = 0;
   out_2289925118654541475[32] = 0;
   out_2289925118654541475[33] = 0;
   out_2289925118654541475[34] = 0;
   out_2289925118654541475[35] = 0;
   out_2289925118654541475[36] = 0;
   out_2289925118654541475[37] = 0;
   out_2289925118654541475[38] = 0;
   out_2289925118654541475[39] = 0;
   out_2289925118654541475[40] = 1;
   out_2289925118654541475[41] = 0;
   out_2289925118654541475[42] = 0;
   out_2289925118654541475[43] = 0;
   out_2289925118654541475[44] = 0;
   out_2289925118654541475[45] = dt*(stiffness_front*(-state[2] - state[3] + state[7])/(mass*state[1]) + (-stiffness_front - stiffness_rear)*state[5]/(mass*state[4]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[6]/(mass*state[4]));
   out_2289925118654541475[46] = -dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*pow(state[1], 2));
   out_2289925118654541475[47] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_2289925118654541475[48] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_2289925118654541475[49] = dt*((-1 - (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*pow(state[4], 2)))*state[6] - (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*pow(state[4], 2)));
   out_2289925118654541475[50] = dt*(-stiffness_front*state[0] - stiffness_rear*state[0])/(mass*state[4]) + 1;
   out_2289925118654541475[51] = dt*(-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]));
   out_2289925118654541475[52] = dt*stiffness_front*state[0]/(mass*state[1]);
   out_2289925118654541475[53] = -9.8000000000000007*dt;
   out_2289925118654541475[54] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front - pow(center_to_rear, 2)*stiffness_rear)*state[6]/(rotational_inertia*state[4]));
   out_2289925118654541475[55] = -center_to_front*dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*pow(state[1], 2));
   out_2289925118654541475[56] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_2289925118654541475[57] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_2289925118654541475[58] = dt*(-(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*pow(state[4], 2)) - (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*pow(state[4], 2)));
   out_2289925118654541475[59] = dt*(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(rotational_inertia*state[4]);
   out_2289925118654541475[60] = dt*(-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])/(rotational_inertia*state[4]) + 1;
   out_2289925118654541475[61] = center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_2289925118654541475[62] = 0;
   out_2289925118654541475[63] = 0;
   out_2289925118654541475[64] = 0;
   out_2289925118654541475[65] = 0;
   out_2289925118654541475[66] = 0;
   out_2289925118654541475[67] = 0;
   out_2289925118654541475[68] = 0;
   out_2289925118654541475[69] = 0;
   out_2289925118654541475[70] = 1;
   out_2289925118654541475[71] = 0;
   out_2289925118654541475[72] = 0;
   out_2289925118654541475[73] = 0;
   out_2289925118654541475[74] = 0;
   out_2289925118654541475[75] = 0;
   out_2289925118654541475[76] = 0;
   out_2289925118654541475[77] = 0;
   out_2289925118654541475[78] = 0;
   out_2289925118654541475[79] = 0;
   out_2289925118654541475[80] = 1;
}
void h_25(double *state, double *unused, double *out_5410238510330826868) {
   out_5410238510330826868[0] = state[6];
}
void H_25(double *state, double *unused, double *out_8287009551490118217) {
   out_8287009551490118217[0] = 0;
   out_8287009551490118217[1] = 0;
   out_8287009551490118217[2] = 0;
   out_8287009551490118217[3] = 0;
   out_8287009551490118217[4] = 0;
   out_8287009551490118217[5] = 0;
   out_8287009551490118217[6] = 1;
   out_8287009551490118217[7] = 0;
   out_8287009551490118217[8] = 0;
}
void h_24(double *state, double *unused, double *out_1692969476607221108) {
   out_1692969476607221108[0] = state[4];
   out_1692969476607221108[1] = state[5];
}
void H_24(double *state, double *unused, double *out_6601808923417110263) {
   out_6601808923417110263[0] = 0;
   out_6601808923417110263[1] = 0;
   out_6601808923417110263[2] = 0;
   out_6601808923417110263[3] = 0;
   out_6601808923417110263[4] = 1;
   out_6601808923417110263[5] = 0;
   out_6601808923417110263[6] = 0;
   out_6601808923417110263[7] = 0;
   out_6601808923417110263[8] = 0;
   out_6601808923417110263[9] = 0;
   out_6601808923417110263[10] = 0;
   out_6601808923417110263[11] = 0;
   out_6601808923417110263[12] = 0;
   out_6601808923417110263[13] = 0;
   out_6601808923417110263[14] = 1;
   out_6601808923417110263[15] = 0;
   out_6601808923417110263[16] = 0;
   out_6601808923417110263[17] = 0;
}
void h_30(double *state, double *unused, double *out_7611026518852293304) {
   out_7611026518852293304[0] = state[4];
}
void H_30(double *state, double *unused, double *out_7641401563712184772) {
   out_7641401563712184772[0] = 0;
   out_7641401563712184772[1] = 0;
   out_7641401563712184772[2] = 0;
   out_7641401563712184772[3] = 0;
   out_7641401563712184772[4] = 1;
   out_7641401563712184772[5] = 0;
   out_7641401563712184772[6] = 0;
   out_7641401563712184772[7] = 0;
   out_7641401563712184772[8] = 0;
}
void h_26(double *state, double *unused, double *out_6628942425516995192) {
   out_6628942425516995192[0] = state[7];
}
void H_26(double *state, double *unused, double *out_6855208552458632798) {
   out_6855208552458632798[0] = 0;
   out_6855208552458632798[1] = 0;
   out_6855208552458632798[2] = 0;
   out_6855208552458632798[3] = 0;
   out_6855208552458632798[4] = 0;
   out_6855208552458632798[5] = 0;
   out_6855208552458632798[6] = 0;
   out_6855208552458632798[7] = 1;
   out_6855208552458632798[8] = 0;
}
void h_27(double *state, double *unused, double *out_1592524193462238911) {
   out_1592524193462238911[0] = state[3];
}
void H_27(double *state, double *unused, double *out_8630579198196941933) {
   out_8630579198196941933[0] = 0;
   out_8630579198196941933[1] = 0;
   out_8630579198196941933[2] = 0;
   out_8630579198196941933[3] = 1;
   out_8630579198196941933[4] = 0;
   out_8630579198196941933[5] = 0;
   out_8630579198196941933[6] = 0;
   out_8630579198196941933[7] = 0;
   out_8630579198196941933[8] = 0;
}
void h_29(double *state, double *unused, double *out_2648646521171000072) {
   out_2648646521171000072[0] = state[1];
}
void H_29(double *state, double *unused, double *out_7131170219397792588) {
   out_7131170219397792588[0] = 0;
   out_7131170219397792588[1] = 1;
   out_7131170219397792588[2] = 0;
   out_7131170219397792588[3] = 0;
   out_7131170219397792588[4] = 0;
   out_7131170219397792588[5] = 0;
   out_7131170219397792588[6] = 0;
   out_7131170219397792588[7] = 0;
   out_7131170219397792588[8] = 0;
}
void h_28(double *state, double *unused, double *out_4629310244906571596) {
   out_4629310244906571596[0] = state[0];
}
void H_28(double *state, double *unused, double *out_6233174837242228454) {
   out_6233174837242228454[0] = 1;
   out_6233174837242228454[1] = 0;
   out_6233174837242228454[2] = 0;
   out_6233174837242228454[3] = 0;
   out_6233174837242228454[4] = 0;
   out_6233174837242228454[5] = 0;
   out_6233174837242228454[6] = 0;
   out_6233174837242228454[7] = 0;
   out_6233174837242228454[8] = 0;
}
void h_31(double *state, double *unused, double *out_2471034140423222317) {
   out_2471034140423222317[0] = state[8];
}
void H_31(double *state, double *unused, double *out_3919298130382710517) {
   out_3919298130382710517[0] = 0;
   out_3919298130382710517[1] = 0;
   out_3919298130382710517[2] = 0;
   out_3919298130382710517[3] = 0;
   out_3919298130382710517[4] = 0;
   out_3919298130382710517[5] = 0;
   out_3919298130382710517[6] = 0;
   out_3919298130382710517[7] = 0;
   out_3919298130382710517[8] = 1;
}
#include <eigen3/Eigen/Dense>
#include <iostream>

typedef Eigen::Matrix<double, DIM, DIM, Eigen::RowMajor> DDM;
typedef Eigen::Matrix<double, EDIM, EDIM, Eigen::RowMajor> EEM;
typedef Eigen::Matrix<double, DIM, EDIM, Eigen::RowMajor> DEM;

void predict(double *in_x, double *in_P, double *in_Q, double dt) {
  typedef Eigen::Matrix<double, MEDIM, MEDIM, Eigen::RowMajor> RRM;

  double nx[DIM] = {0};
  double in_F[EDIM*EDIM] = {0};

  // functions from sympy
  f_fun(in_x, dt, nx);
  F_fun(in_x, dt, in_F);


  EEM F(in_F);
  EEM P(in_P);
  EEM Q(in_Q);

  RRM F_main = F.topLeftCorner(MEDIM, MEDIM);
  P.topLeftCorner(MEDIM, MEDIM) = (F_main * P.topLeftCorner(MEDIM, MEDIM)) * F_main.transpose();
  P.topRightCorner(MEDIM, EDIM - MEDIM) = F_main * P.topRightCorner(MEDIM, EDIM - MEDIM);
  P.bottomLeftCorner(EDIM - MEDIM, MEDIM) = P.bottomLeftCorner(EDIM - MEDIM, MEDIM) * F_main.transpose();

  P = P + dt*Q;

  // copy out state
  memcpy(in_x, nx, DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
}

// note: extra_args dim only correct when null space projecting
// otherwise 1
template <int ZDIM, int EADIM, bool MAHA_TEST>
void update(double *in_x, double *in_P, Hfun h_fun, Hfun H_fun, Hfun Hea_fun, double *in_z, double *in_R, double *in_ea, double MAHA_THRESHOLD) {
  typedef Eigen::Matrix<double, ZDIM, ZDIM, Eigen::RowMajor> ZZM;
  typedef Eigen::Matrix<double, ZDIM, DIM, Eigen::RowMajor> ZDM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, EDIM, Eigen::RowMajor> XEM;
  //typedef Eigen::Matrix<double, EDIM, ZDIM, Eigen::RowMajor> EZM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, 1> X1M;
  typedef Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor> XXM;

  double in_hx[ZDIM] = {0};
  double in_H[ZDIM * DIM] = {0};
  double in_H_mod[EDIM * DIM] = {0};
  double delta_x[EDIM] = {0};
  double x_new[DIM] = {0};


  // state x, P
  Eigen::Matrix<double, ZDIM, 1> z(in_z);
  EEM P(in_P);
  ZZM pre_R(in_R);

  // functions from sympy
  h_fun(in_x, in_ea, in_hx);
  H_fun(in_x, in_ea, in_H);
  ZDM pre_H(in_H);

  // get y (y = z - hx)
  Eigen::Matrix<double, ZDIM, 1> pre_y(in_hx); pre_y = z - pre_y;
  X1M y; XXM H; XXM R;
  if (Hea_fun){
    typedef Eigen::Matrix<double, ZDIM, EADIM, Eigen::RowMajor> ZAM;
    double in_Hea[ZDIM * EADIM] = {0};
    Hea_fun(in_x, in_ea, in_Hea);
    ZAM Hea(in_Hea);
    XXM A = Hea.transpose().fullPivLu().kernel();


    y = A.transpose() * pre_y;
    H = A.transpose() * pre_H;
    R = A.transpose() * pre_R * A;
  } else {
    y = pre_y;
    H = pre_H;
    R = pre_R;
  }
  // get modified H
  H_mod_fun(in_x, in_H_mod);
  DEM H_mod(in_H_mod);
  XEM H_err = H * H_mod;

  // Do mahalobis distance test
  if (MAHA_TEST){
    XXM a = (H_err * P * H_err.transpose() + R).inverse();
    double maha_dist = y.transpose() * a * y;
    if (maha_dist > MAHA_THRESHOLD){
      R = 1.0e16 * R;
    }
  }

  // Outlier resilient weighting
  double weight = 1;//(1.5)/(1 + y.squaredNorm()/R.sum());

  // kalman gains and I_KH
  XXM S = ((H_err * P) * H_err.transpose()) + R/weight;
  XEM KT = S.fullPivLu().solve(H_err * P.transpose());
  //EZM K = KT.transpose(); TODO: WHY DOES THIS NOT COMPILE?
  //EZM K = S.fullPivLu().solve(H_err * P.transpose()).transpose();
  //std::cout << "Here is the matrix rot:\n" << K << std::endl;
  EEM I_KH = Eigen::Matrix<double, EDIM, EDIM>::Identity() - (KT.transpose() * H_err);

  // update state by injecting dx
  Eigen::Matrix<double, EDIM, 1> dx(delta_x);
  dx  = (KT.transpose() * y);
  memcpy(delta_x, dx.data(), EDIM * sizeof(double));
  err_fun(in_x, delta_x, x_new);
  Eigen::Matrix<double, DIM, 1> x(x_new);

  // update cov
  P = ((I_KH * P) * I_KH.transpose()) + ((KT.transpose() * R) * KT);

  // copy out state
  memcpy(in_x, x.data(), DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
  memcpy(in_z, y.data(), y.rows() * sizeof(double));
}




}
extern "C" {

void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_25, H_25, NULL, in_z, in_R, in_ea, MAHA_THRESH_25);
}
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<2, 3, 0>(in_x, in_P, h_24, H_24, NULL, in_z, in_R, in_ea, MAHA_THRESH_24);
}
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_30, H_30, NULL, in_z, in_R, in_ea, MAHA_THRESH_30);
}
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_26, H_26, NULL, in_z, in_R, in_ea, MAHA_THRESH_26);
}
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_27, H_27, NULL, in_z, in_R, in_ea, MAHA_THRESH_27);
}
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_29, H_29, NULL, in_z, in_R, in_ea, MAHA_THRESH_29);
}
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_28, H_28, NULL, in_z, in_R, in_ea, MAHA_THRESH_28);
}
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_31, H_31, NULL, in_z, in_R, in_ea, MAHA_THRESH_31);
}
void car_err_fun(double *nom_x, double *delta_x, double *out_7013090005465437157) {
  err_fun(nom_x, delta_x, out_7013090005465437157);
}
void car_inv_err_fun(double *nom_x, double *true_x, double *out_7341665202261006375) {
  inv_err_fun(nom_x, true_x, out_7341665202261006375);
}
void car_H_mod_fun(double *state, double *out_1371433892673034290) {
  H_mod_fun(state, out_1371433892673034290);
}
void car_f_fun(double *state, double dt, double *out_3433941462029035336) {
  f_fun(state,  dt, out_3433941462029035336);
}
void car_F_fun(double *state, double dt, double *out_2289925118654541475) {
  F_fun(state,  dt, out_2289925118654541475);
}
void car_h_25(double *state, double *unused, double *out_5410238510330826868) {
  h_25(state, unused, out_5410238510330826868);
}
void car_H_25(double *state, double *unused, double *out_8287009551490118217) {
  H_25(state, unused, out_8287009551490118217);
}
void car_h_24(double *state, double *unused, double *out_1692969476607221108) {
  h_24(state, unused, out_1692969476607221108);
}
void car_H_24(double *state, double *unused, double *out_6601808923417110263) {
  H_24(state, unused, out_6601808923417110263);
}
void car_h_30(double *state, double *unused, double *out_7611026518852293304) {
  h_30(state, unused, out_7611026518852293304);
}
void car_H_30(double *state, double *unused, double *out_7641401563712184772) {
  H_30(state, unused, out_7641401563712184772);
}
void car_h_26(double *state, double *unused, double *out_6628942425516995192) {
  h_26(state, unused, out_6628942425516995192);
}
void car_H_26(double *state, double *unused, double *out_6855208552458632798) {
  H_26(state, unused, out_6855208552458632798);
}
void car_h_27(double *state, double *unused, double *out_1592524193462238911) {
  h_27(state, unused, out_1592524193462238911);
}
void car_H_27(double *state, double *unused, double *out_8630579198196941933) {
  H_27(state, unused, out_8630579198196941933);
}
void car_h_29(double *state, double *unused, double *out_2648646521171000072) {
  h_29(state, unused, out_2648646521171000072);
}
void car_H_29(double *state, double *unused, double *out_7131170219397792588) {
  H_29(state, unused, out_7131170219397792588);
}
void car_h_28(double *state, double *unused, double *out_4629310244906571596) {
  h_28(state, unused, out_4629310244906571596);
}
void car_H_28(double *state, double *unused, double *out_6233174837242228454) {
  H_28(state, unused, out_6233174837242228454);
}
void car_h_31(double *state, double *unused, double *out_2471034140423222317) {
  h_31(state, unused, out_2471034140423222317);
}
void car_H_31(double *state, double *unused, double *out_3919298130382710517) {
  H_31(state, unused, out_3919298130382710517);
}
void car_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
void car_set_mass(double x) {
  set_mass(x);
}
void car_set_rotational_inertia(double x) {
  set_rotational_inertia(x);
}
void car_set_center_to_front(double x) {
  set_center_to_front(x);
}
void car_set_center_to_rear(double x) {
  set_center_to_rear(x);
}
void car_set_stiffness_front(double x) {
  set_stiffness_front(x);
}
void car_set_stiffness_rear(double x) {
  set_stiffness_rear(x);
}
}

const EKF car = {
  .name = "car",
  .kinds = { 25, 24, 30, 26, 27, 29, 28, 31 },
  .feature_kinds = {  },
  .f_fun = car_f_fun,
  .F_fun = car_F_fun,
  .err_fun = car_err_fun,
  .inv_err_fun = car_inv_err_fun,
  .H_mod_fun = car_H_mod_fun,
  .predict = car_predict,
  .hs = {
    { 25, car_h_25 },
    { 24, car_h_24 },
    { 30, car_h_30 },
    { 26, car_h_26 },
    { 27, car_h_27 },
    { 29, car_h_29 },
    { 28, car_h_28 },
    { 31, car_h_31 },
  },
  .Hs = {
    { 25, car_H_25 },
    { 24, car_H_24 },
    { 30, car_H_30 },
    { 26, car_H_26 },
    { 27, car_H_27 },
    { 29, car_H_29 },
    { 28, car_H_28 },
    { 31, car_H_31 },
  },
  .updates = {
    { 25, car_update_25 },
    { 24, car_update_24 },
    { 30, car_update_30 },
    { 26, car_update_26 },
    { 27, car_update_27 },
    { 29, car_update_29 },
    { 28, car_update_28 },
    { 31, car_update_31 },
  },
  .Hes = {
  },
  .sets = {
    { "mass", car_set_mass },
    { "rotational_inertia", car_set_rotational_inertia },
    { "center_to_front", car_set_center_to_front },
    { "center_to_rear", car_set_center_to_rear },
    { "stiffness_front", car_set_stiffness_front },
    { "stiffness_rear", car_set_stiffness_rear },
  },
  .extra_routines = {
  },
};

ekf_lib_init(car)
