#!/usr/bin/python

## \file Solver.py
#  \brief Implementation of basis class to solve the slice acquisition model
#  \f[ 
#       y_k = D_k B_k W_k x = A_k x 
#  \f]
#  for each slice \f$ y_k,\,k=1,\dots,K \f$ during reconstruction
#
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date July 2016


## Import libraries
from abc import ABCMeta, abstractmethod
import sys
import itk
import SimpleITK as sitk
import numpy as np
from scipy.sparse.linalg import LinearOperator
from scipy.sparse.linalg import lsqr
from scipy.sparse.linalg import lsmr
from scipy.optimize import lsq_linear
from scipy.optimize import minimize
from scipy.optimize import least_squares
from scipy.optimize import nnls


## Import modules
import utilities.SimpleITKHelper as sitkh
import reconstruction.solver.DifferentialOperations as diffop
import base.PSF as psf

## Pixel type of used 3D ITK image
PIXEL_TYPE = itk.D

## ITK image type
IMAGE_TYPE = itk.Image[PIXEL_TYPE, 3]


class Solver(object):
    __metaclass__ = ABCMeta
    
    """ This class contains the common functions/attributes of the solvers """

    ##
    #          Constructor
    # \date          2016-08-01 22:53:37+0100
    #
    # \param         self                   The object
    # \param[in]     stacks                 list of Stack objects containing
    #                                       all stacks used for the
    #                                       reconstruction
    # \param[in,out] HR_volume              Stack object containing the current
    #                                       estimate of the HR volume (used as
    #                                       initial value + space definition)
    # \param[in]     alpha_cut              Cut-off distance for Gaussian
    #                                       blurring filter
    # \param[in]     alpha                  regularization parameter, scalar
    # \param[in]     iter_max               number of maximum iterations,
    #                                       scalar
    # \param[in]     deconvolution_mode     Either "full_3D" or
    #                                       "only_in_plane". Indicates whether
    #                                       full 3D or only in-plane
    #                                       deconvolution is considered
    # \param[in]     predefined_covariance  Either only diagonal entries
    #                                       (sigma_x2, sigma_y2, sigma_z2) or
    #                                       as full 3x3 numpy array
    #
    def __init__(self, stacks, HR_volume, alpha_cut=3, alpha=0.02, iter_max=10, minimizer="lsmr", deconvolution_mode="full_3D", predefined_covariance=None):

        ## Initialize variables
        self._stacks = stacks
        self._HR_volume = HR_volume
        self._N_stacks = len(stacks)

        ## Used for PSF modelling
        self._psf = psf.PSF()

        self._deconvolution_mode = deconvolution_mode
        self._update_oriented_adjoint_oriented_Gaussian_image_filters = {
            "full_3D":                  self._update_oriented_adjoint_oriented_Gaussian_image_filters_full_3D,
            "only_in_plane":            self._update_oriented_adjoint_oriented_Gaussian_image_filters_in_plane,
            "predefined_covariance":    self._update_oriented_adjoint_oriented_Gaussian_image_filters_predefined_covariance
        }

        self._minimizer = minimizer
        self._get_approximate_solution = {
            ## linear least-squares
            "lsmr"          : self._get_approximate_solution_lsmr,
            "lsqr"          : self._get_approximate_solution_lsqr,

            ## non-negative linear least-squares
            "nnls"          : self._get_approximate_solution_nnls,

            ## linear least-squares solver with bounds
            "lsq_linear"    : self._get_approximate_solution_lsq_linear,
             
            ## non-linear solver with bounds
            "L-BFGS-B"      : self._get_approximate_solution_LBFGSB,
            "least_squares" : self._get_approximate_solution_least_squares,
        }

        ## In case only diagonal entries are given, create diagonal matrix
        if predefined_covariance is not None:
            ## Convert to numpy array if required
            predefined_covariance = np.array(predefined_covariance)
            
            if predefined_covariance.size is 3:
                predefined_covariance = np.diag(predefined_covariance)
        self._predefined_covariance = predefined_covariance

        ## Idea: Set through-plane spacing artificially very small so that the 
        ## corresponding becomes negligibly small in through-plane direction. 
        ## Hence, only in-plane deconvolution is approximated.
        self._deconvolution_only_in_plane_through_plane_spacing = 1e-6

        ## Cut-off distance for Gaussian blurring filter
        self._alpha_cut = alpha_cut  

        ## Settings for solver
        self._alpha = alpha
        self._iter_max = iter_max

        ## Allocate and initialize Oriented Gaussian Interpolate Image Filter
        self._filter_oriented_Gaussian = itk.OrientedGaussianInterpolateImageFilter[IMAGE_TYPE, IMAGE_TYPE].New()
        self._filter_oriented_Gaussian.SetDefaultPixelValue(0.0)
        self._filter_oriented_Gaussian.SetAlpha(self._alpha_cut)

        ## Allocate and initialize Adjoint Oriented Gaussian Interpolate Image Filter
        self._filter_adjoint_oriented_Gaussian = itk.AdjointOrientedGaussianInterpolateImageFilter[IMAGE_TYPE, IMAGE_TYPE].New()
        self._filter_adjoint_oriented_Gaussian.SetDefaultPixelValue(0.0)
        self._filter_adjoint_oriented_Gaussian.SetAlpha(self._alpha_cut)
        self._filter_adjoint_oriented_Gaussian.SetOutputParametersFromImage(self._HR_volume.itk)

        ## Create PyBuffer object for conversion between NumPy arrays and ITK images
        self._itk2np = itk.PyBuffer[IMAGE_TYPE]

        ## Extract information ready to use for itk image conversion operations
        self._HR_shape_nda = sitk.GetArrayFromImage(self._HR_volume.sitk).shape

        ## Define differential operators
        spacing = self._HR_volume.sitk.GetSpacing()[0]
        self._differential_operations = diffop.DifferentialOperations(step_size=spacing)   

        """
        Helpers
        """
        ## Compute total amount of pixels for all slices
        self._N_total_slice_voxels = 0
        for i in range(0, self._N_stacks):
            N_stack_voxels = np.array(self._stacks[i].sitk.GetSize()).prod()
            self._N_total_slice_voxels += N_stack_voxels

        ## Compute total amount of voxels of x:
        self._N_voxels_HR_volume = np.array(self._HR_volume.sitk.GetSize()).prod()

        ## Allocate variables conataining information about statistics of reconstruction
        self._elapsed_time_sec = None
        self._residual_ell2 = None
        self._residual_prior = None


    ## Set regularization parameter for Tikhonov regularization
    #  \param[in] alpha regularization parameter, scalar
    def set_alpha(self, alpha):
        self._alpha = alpha


    ## Get value of chosen regularization parameter for Tikhonov regularization
    #  \return regularization parameter, scalar
    def get_alpha(self):
        return self._alpha


    ##
    #       Sets the maximum number of iterations for Tikhonov solver.
    # \date       2016-08-01 16:35:09+0100
    #
    # \param      self      The object
    # \param[in]  iter_max  number of maximum iterations, scalar
    #
    def set_iter_max(self, iter_max):
        self._iter_max = iter_max


    ## Get chosen value of maximum number of iterations for minimizer for Tikhonov regularization
    #  \return maximum number of iterations set for minimizer, scalar
    def get_iter_max(self):
        return self._iter_max


    ##
    #       Sets the minimizer.
    # \date       2016-11-05 23:40:31+0000
    #
    # \param      self       The object
    # \param      minimizer  The minimizer
    #
    def set_minimizer(self, minimizer):
        self._minimizer = minimizer


    def get_minimizer(self):
        return self._minimizer


    ## Get current estimate of HR volume
    #  \return current estimate of HR volume, instance of Stack
    def get_reconstruction(self):
        return self._HR_volume


    ## Set cut-off distance
    #  \param[in] alpha_cut scalar value
    def set_alpha_cut(self, alpha_cut):
        self._alpha_cut = alpha_cut

        ## Update filters        
        self._filter_oriented_Gaussian.SetAlpha(self._alpha_cut)
        self._filter_adjoint_oriented_Gaussian.SetAlpha(self._alpha_cut)


    ## Get cut-off distance
    #  \return scalar value
    def get_alpha_cut(self):
        return self._alpha_cut


    ## Get computational time for reconstruction
    #  \return computational time in seconds
    def get_computational_time(self):
        if self._elapsed_time_sec < 0:
            raise ValueError("Error: Elapsed time has not been measured. Run 'run_reconstruction' first.")
        return self._elapsed_time_sec


    ## Get \f$\ell^2\f$-residual for performed reconstruction
    #  \return \f$\ell^2\f$-residual
    def get_residual_ell2(self):
        if self._residual_ell2 < 0:
            raise ValueError("Error: Residual has not been computed yet. Run 'compute_statistics' first.")

        return self._residual_ell2


    ## Get prior-residual for performed reconstruction
    #  \return \f$\ell^2\f$-residual
    def get_residual_prior(self):
        if self._residual_prior < 0:
            raise ValueError("Error: Residual has not been computed yet. Run 'compute_statistics' first.")

        return self._residual_prior


    ##
    #       Gets the setting specific filename indicating the information
    #             used for the reconstruction step
    # \date       2016-11-17 15:41:58+0000
    #
    # \param      self    The object
    # \param      prefix  The prefix as string
    #
    # \return     The setting specific filename as string.
    #
    @abstractmethod
    def get_setting_specific_filename(self, prefix=""):
        pass

    ##
    #       Sets the predefined covariance matrix, representing
    #             slice-axis aligned Gaussian blurring covariance.
    # \date       2016-10-14 16:49:41+0100
    #
    # \param      self  The object
    # \param      cov   Either only diagonal entries (sigma_x2, sigma_y2,
    #                   sigma_z2) or as full 3x3 numpy array
    #
    def set_predefined_covariance(self, cov):

        ## Convert to numpy array if required
        cov = np.array(cov)

        ## In case only diagonal entries are given, create diagonal matrix
        if cov.size is 3:
            cov = np.diag(cov)
        self._predefined_covariance = cov

    ##
    #       Gets the predefined covariance.
    # \date       2016-10-14 16:52:10+0100
    #
    # \param      self  The object
    #
    # \return     The predefined covariance as 3x3 numpy array
    #
    def get_predefined_covariance(self):
        return self._predefined_covariance


    ## Update internal Oriented and Adjoint Oriented Gaussian Interpolate Image
    #  Filter parameters. Hence, update combined Downsample and Blur Operator
    #  according to the relative position between slice and HR volume.
    #  \param[in] slice Slice object
    def _update_oriented_adjoint_oriented_Gaussian_image_filters_full_3D(self, slice):
        ## Get variance covariance matrix representing Gaussian blurring in HR volume coordinates
        Cov_HR_coord = self._psf.get_gaussian_PSF_covariance_matrix_HR_volume_coordinates(slice, self._HR_volume)

        ## Update parameters of forward operator A
        self._filter_oriented_Gaussian.SetCovariance(Cov_HR_coord.flatten())
        self._filter_oriented_Gaussian.SetOutputParametersFromImage(slice.itk)
        
        ## Update parameters of backward/adjoint operator A'
        self._filter_adjoint_oriented_Gaussian.SetCovariance(Cov_HR_coord.flatten())


    ## Update internal Oriented and Adjoint Oriented Gaussian Interpolate Image
    #  Filter parameters. Hence, update combined Downsample and Blur Operator
    #  according to the relative position between slice and HR volume.
    #  BUT, only consider in-plane deconvolution (Was added for the MS project)
    #  \param[in] slice Slice object
    def _update_oriented_adjoint_oriented_Gaussian_image_filters_in_plane(self, slice):

        ## Get spacing of slice and set it very small so that the corresponding
        ## covariance is negligibly small in through-plane direction. Hence,
        ## only in-plane deconvolution is approximated
        spacing = np.array(slice.sitk.GetSpacing())
        spacing[2] = self._deconvolution_only_in_plane_through_plane_spacing
        direction = np.array(slice.sitk.GetDirection())

        ## Get variance covariance matrix representing Gaussian blurring in HR volume coordinates
        Cov_HR_coord = self._psf.get_gaussian_PSF_covariance_matrix_HR_volume_coordinates_from_direction_and_spacing(direction, spacing, self._HR_volume)

        ## Update parameters of forward operator A
        self._filter_oriented_Gaussian.SetCovariance(Cov_HR_coord.flatten())
        self._filter_oriented_Gaussian.SetOutputParametersFromImage(slice.itk)
        
        ## Update parameters of backward/adjoint operator A'
        self._filter_adjoint_oriented_Gaussian.SetCovariance(Cov_HR_coord.flatten())


    ## Update internal Oriented and Adjoint Oriented Gaussian Interpolate Image
    #  Filter parameters. Hence, update combined Downsample and Blur Operator
    #  according to the relative position between slice and HR volume.
    #  BUT, predefined covariance used (Was added for the MS project)
    #  \param[in] slice Slice object
    def _update_oriented_adjoint_oriented_Gaussian_image_filters_predefined_covariance(self, slice):

        ## Get variance covariance matrix representing Gaussian blurring in HR volume coordinates
        Cov_HR_coord = self._psf.get_gaussian_PSF_covariance_matrix_HR_volume_coordinates_from_covariances(slice, self._HR_volume, self._predefined_covariance)

        ## Update parameters of forward operator A
        self._filter_oriented_Gaussian.SetCovariance(Cov_HR_coord.flatten())
        self._filter_oriented_Gaussian.SetOutputParametersFromImage(slice.itk)
        
        ## Update parameters of backward/adjoint operator A'
        self._filter_adjoint_oriented_Gaussian.SetCovariance(Cov_HR_coord.flatten())


    ## Perform forward operation on HR image, i.e. 
    #  \f$y_k = D_k B_k x =: A_k x \f$ with \f$D_k\f$  and \f$ B_k \f$ being 
    #  the downsampling and blurring operator, respectively.
    #  \param[in] HR_volume_itk HR image as itk.Image object
    #  \param[in] slice_k Slice object which defines operator A_k
    #  \return image in LR space as itk.Image object after performed forward operation
    def _Ak(self, HR_volume_itk, slice_k):

        ## Set up operator A_k based on relative position to HR volume and their dimensions
        self._update_oriented_adjoint_oriented_Gaussian_image_filters[self._deconvolution_mode](slice_k)

        ## Perform forward operation A_k on HR volume object
        HR_volume_itk.Update()
        self._filter_oriented_Gaussian.SetInput(HR_volume_itk)
        self._filter_oriented_Gaussian.UpdateLargestPossibleRegion()
        self._filter_oriented_Gaussian.Update()

        slice_itk = self._filter_oriented_Gaussian.GetOutput();
        slice_itk.DisconnectPipeline()

        return slice_itk


    ## Perform backward operation on LR image, i.e. 
    #  \f$z_k = B_k^*D_k^*y = A_k^y \f$ with \f$ D_k^* \f$ and \f$ B_k^* \f$ being 
    #  the adjoint downsampling and blurring operator, respectively.
    #  \param[in] slice_itk LR image as itk.Image object
    #  \param[in] slice_k Slice object which defines operator A_k^*
    #  \return image in HR space as itk.Image object after performed backward operation
    def _Ak_adj(self, slice_itk, slice_k):

        ## Set up operator A_k^* based on relative position to HR volume and their dimensions
        self._update_oriented_adjoint_oriented_Gaussian_image_filters[self._deconvolution_mode](slice_k)

        ## Perform backward operation A_k^* on LR image object
        self._filter_adjoint_oriented_Gaussian.SetInput(slice_itk)
        self._filter_adjoint_oriented_Gaussian.UpdateLargestPossibleRegion()
        self._filter_adjoint_oriented_Gaussian.Update()

        HR_volume_itk = self._filter_adjoint_oriented_Gaussian.GetOutput()
        HR_volume_itk.DisconnectPipeline()

        return HR_volume_itk


    ## Evaluate \f$ D \vec{x} \f$
    #  \f$ = \begin{pmatrix} D_x \\ D_y \\ D_z \end{pmatrix} \vec{x}\f$
    #  within the adjoint augmented linear operator for TK1-regularization.
    #  \param[in] HR_nda_vec HR data as 1D array
    #  \return evaluated differential operator as part of
    #       augmented linear operator as 1D array
    def _D(self, HR_nda_vec):

        ## Number of voxels always given by 3 times HR voxels
        N_voxels = self._N_voxels_HR_volume

        ## Allocate memory
        D_x = np.zeros(3*N_voxels)

        HR_nda = HR_nda_vec.reshape(self._HR_shape_nda)

        ## Differentiate w.r.t. x, y and z and fill corresponding indices
        D_x[0:N_voxels] = self._differential_operations.Dx(HR_nda).flatten()
        D_x[N_voxels:2*N_voxels] = self._differential_operations.Dy(HR_nda).flatten()
        D_x[2*N_voxels:3*N_voxels] = self._differential_operations.Dz(HR_nda).flatten()

        return D_x


    ## Evaluate \f$ D^* \vec{y} \f$
    #  \f$ = \begin{pmatrix} D_x^* && D_y && D_z \end{pmatrix} \vec{y}\in\mathbb{R}^N\f$
    #  within the adjoint augmented linear operator for TK1-regularization.
    #  \param[in] stacked_slices_nda_vec stacked slice data as 1D array
    #  \return evaluated adjoint differential operator as part of
    #       augmented adjoint linear operator as 1D array
    def _D_adj(self, stacked_slices_nda_vec):

        ## Get helpers to index correct elements
        N_vol = self._N_voxels_HR_volume
        N0 = self._N_total_slice_voxels

        ## Extract respective x, y and z groups within compound stacked_slices_nda_vec
        slice_x_nda_vec = stacked_slices_nda_vec[N0:N0+N_vol]
        slice_y_nda_vec = stacked_slices_nda_vec[N0+N_vol:N0+2*N_vol]
        slice_z_nda_vec = stacked_slices_nda_vec[N0+2*N_vol:N0+3*N_vol]

        ## Reshape in order to apply differentiation
        slice_x_nda = slice_x_nda_vec.reshape(self._HR_shape_nda)
        slice_y_nda = slice_y_nda_vec.reshape(self._HR_shape_nda)
        slice_z_nda = slice_z_nda_vec.reshape(self._HR_shape_nda)

        ## Apply adjoint differentiation w.r.t. x, y and z
        Dx_adj_vec = self._differential_operations.Dx_adj(slice_x_nda).flatten()
        Dy_adj_vec = self._differential_operations.Dy_adj(slice_y_nda).flatten()
        Dz_adj_vec = self._differential_operations.Dz_adj(slice_z_nda).flatten()

        ## Return added contributions 
        return  Dx_adj_vec + Dy_adj_vec + Dz_adj_vec


    ## Masking operation M_k
    #  \param[in] slice_itk image in LR space as itk.Image object
    #  \param[in] slice_k Slice object which defines operator M_k
    def _Mk(self, slice_itk, slice_k):

        ## Perform masking M_k based
        multiplier = itk.MultiplyImageFilter[IMAGE_TYPE, IMAGE_TYPE, IMAGE_TYPE].New()
        multiplier.SetInput1(slice_k.itk_mask)
        multiplier.SetInput2(slice_itk)
        multiplier.Update()

        Mk_slice_itk = multiplier.GetOutput()
        Mk_slice_itk.DisconnectPipeline()

        return Mk_slice_itk


    ## Evaluate \f$ M \vec{y} \f$
    #  \f$ = \begin{pmatrix} M_1 \vec{y}_1 \\ M_2 \vec{y}_2 \\ \vdots \\ M_K \vec{y}_K \end{pmatrix} \vec{x}\f$
    #  \return My, i.e. all masked slices stacked to 1D array
    def _get_M_y(self):

        ## Allocate memory
        My = np.zeros(self._N_total_slice_voxels)

        ## Define index for first voxel of first slice within array
        i_min = 0

        for i in range(0, self._N_stacks):
            stack = self._stacks[i]
            slices = stack.get_slices()

            ## Get number of voxels of each slice in current stack
            N_slice_voxels = np.array(slices[0].sitk.GetSize()).prod()

            for j in range(0, stack.get_number_of_slices()):

                ## Define index for last voxel to specify current slice (exlusive)
                i_max = i_min + N_slice_voxels

                ## Get current slice
                slice_k = slices[j]

                ## Apply M_k y_k
                slice_itk = self._Mk(slice_k.itk, slice_k)
                slice_nda_vec = self._itk2np.GetArrayFromImage(slice_itk).flatten()

                ## Fill respective elements
                My[i_min:i_max] = slice_nda_vec

                ## Define index for first voxel to specify subsequent slice (inclusive)
                i_min = i_max

        return My


    ## Operation M_k A_k x
    #  \param[in] HR_volume_itk HR image as itk.Image object
    #  \param[in] slice_k Slice object which defines operator M_k and A_k
    def _Mk_Ak(self, HR_volume_itk, slice_k):

        ## Compute A_k x
        Ak_HR_volume_itk = self._Ak(HR_volume_itk, slice_k)

        ## Compute M_k A_k x
        return self._Mk(Ak_HR_volume_itk, slice_k)


    ## Operation A_k^* M_k y_k
    #  \param[in] slice_itk LR image as itk.Image object
    #  \param[in] slice_k Slice object which defines operator A_k^*
    #  \return image in HR space as itk.Image object after performed backward operation
    def _Ak_adj_Mk(self, slice_itk, slice_k):

        ## Compute M_k y_k
        Mk_slice_itk = self._Mk(slice_itk, slice_k)

        ## Compute A_k^* M_k y_k
        return self._Ak_adj(Mk_slice_itk, slice_k)


    ## Evaluate
    #  \f$ MA \vec{x} \f$
    #  \f$ = \begin{pmatrix} M_1 A_1 \\ M_2 A_2 \\ \vdots \\ M_K A_K \end{pmatrix} \vec{x} \f$
    #  \param[in] HR_nda_vec HR data as 1D array
    #  \return evaluated MAx as part of augmented linear operator as 1D array
    def _MA(self, HR_nda_vec):

        ## Convert HR data array back to itk.Image object
        x_itk = self._get_itk_image_from_array_vec(HR_nda_vec, self._HR_volume.itk)
        
        ## Allocate memory
        MA_x = np.zeros(self._N_total_slice_voxels)

        ## Define index for first voxel of first slice within array
        i_min = 0

        for i in range(0, self._N_stacks):
            stack = self._stacks[i]
            slices = stack.get_slices()

            ## Get number of voxels of each slice in current stack
            N_slice_voxels = np.array(slices[0].sitk.GetSize()).prod()

            for j in range(0, stack.get_number_of_slices()):
                
                ## Define index for last voxel to specify current slice (exlusive)
                i_max = i_min + N_slice_voxels

                ## Compute M_k A_k y_k
                slice_itk = self._Mk_Ak(x_itk, slices[j])
                slice_nda = self._itk2np.GetArrayFromImage(slice_itk)

                ## Fill corresponding elements
                MA_x[i_min:i_max] = slice_nda.flatten()

                ## Define index for first voxel to specify subsequent slice (inclusive)
                i_min = i_max

        return MA_x


    ## Evaluate
    #  \f$ A^* M \vec{y}
    #     = \begin{bmatrix} A_1^* M_1 && A_2^* M_2 && \cdots && A_K^* M_K \end{bmatrix} \vec{y}
    #  \f$
    #  \param[in] stacked_slices_nda_vec stacked slice data as 1D array
    #  \return evaluated A'My as part of augmented adjoint linear operator as 1D array
    def _A_adj_M(self, stacked_slices_nda_vec):

        ## Allocate memory
        A_adj_M_y = np.zeros(self._N_voxels_HR_volume)

        ## Define index for first voxel of first slice within array
        i_min = 0

        for i in range(0, self._N_stacks):
            stack = self._stacks[i]
            slices = stack.get_slices()

            ## Get number of voxels of each slice in current stack
            N_slice_voxels = np.array(slices[0].sitk.GetSize()).prod()

            for j in range(0, stack.get_number_of_slices()):

                ## Define index for last voxel to specify current slice (exlusive)
                i_max = i_min + N_slice_voxels

                ## Get current slice
                slice_k = slices[j]

                ## Extract 1D corresponding to current slice and convert it to itk.Object
                slice_itk = self._get_itk_image_from_array_vec(stacked_slices_nda_vec[i_min:i_max], slice_k.itk)

                ## Apply A_k' M_k on current slice
                Ak_adj_Mk_slice_itk = self._Ak_adj_Mk(slice_itk, slice_k)
                Ak_adj_Mk_slice_nda_vec = self._itk2np.GetArrayFromImage(Ak_adj_Mk_slice_itk).flatten()

                ## Add contribution
                A_adj_M_y = A_adj_M_y + Ak_adj_Mk_slice_nda_vec

                ## Define index for first voxel to specify subsequent slice (inclusive)
                i_min = i_max

        return A_adj_M_y


    ## Evaluate augmented linear operator for TK1-regularization, i.e.
    #  \f$
    #       \begin{pmatrix} MA \\ \sqrt{\alpha} G \end{pmatrix} \vec{x}
    #     = \begin{pmatrix} M_1 A_1 \\ M_2 A_2 \\ \vdots \\ M_K A_K \\ \sqrt{\alpha} D \end{pmatrix} \vec{x}
    #  \f$
    #  for \f$ G = D\f$ representing the gradient.
    #  \param[in] HR_nda_vec HR data as 1D array
    #  \param[in] alpha regularization parameter, scalar
    #  \return evaluated augmented linear operator as 1D array
    def _A_TK1(self, HR_nda_vec, alpha):

        ## Get helpers to index correct elements
        N_vol = self._N_voxels_HR_volume
        N0 = self._N_total_slice_voxels

        ## Allocate memory
        A_x = np.zeros(self._N_total_slice_voxels+3*self._N_voxels_HR_volume)

        ## Compute MAx 
        A_x[0:N0] = self._MA(HR_nda_vec)

        ## Compute sqrt(alpha)*Dx
        A_x[N0:N0+3*N_vol] = np.sqrt(alpha)*self._D(HR_nda_vec)

        return A_x


    ## Evaluate the adjoint augmented linear operator for TK1-regularization, i.e.
    #  \f$
    #       \begin{bmatrix} A^* M && \sqrt{\alpha} G^* \end{bmatrix} \vec{y}
    #     = \begin{bmatrix} A_1^* M_1 && A_2^* M_2 && \cdots && A_K^* M_K && \sqrt{\alpha} D^* \end{bmatrix} \vec{y}
    #  \f$
    #  for \f$ G = D\f$ representing the gradient and \f$\vec{y}\in\mathbb{R}^{\sum_k N_k + 3N}\f$ 
    #  representing a vector of stacked slices
    #  \param[in] stacked_slices_nda_vec stacked slice data as 1D array
    #  \param[in] alpha regularization parameter, scalar
    #  \return evaluated augmented adjoint linear operator 
    def _A_adj_TK1(self, stacked_slices_nda_vec, alpha):

        ## Compute A'M y[upper]
        A_adj_y = self._A_adj_M(stacked_slices_nda_vec)

        ## Add D' y[lower]
        A_adj_y = A_adj_y + self._D_adj(stacked_slices_nda_vec).flatten()*np.sqrt(alpha)

        return A_adj_y


    ## Convert numpy data array (vector format) back to itk.Image object
    #  \param[in] HR_nda_vec HR data as 1D array
    #  \return HR volume with intensities according to HR_nda_vec as itk.Image object
    def _get_itk_image_from_array_vec(self, nda_vec, image_itk_ref):
        
        shape_nda = np.array(image_itk_ref.GetLargestPossibleRegion().GetSize())[::-1]

        image_itk = self._itk2np.GetImageFromArray(nda_vec.reshape(shape_nda))
        image_itk.SetOrigin(image_itk_ref.GetOrigin())
        image_itk.SetSpacing(image_itk_ref.GetSpacing())
        image_itk.SetDirection(image_itk_ref.GetDirection())

        return image_itk


    ## Compute the residual \f$ \sum_{k=1}^K \Vert M_k (A_k \vec{x} - \vec{y}_k) \Vert \f$
    #  for \f$ \Vert \cdot \Vert = \Vert \cdot \Vert_{\ell^2}^2 \f$
    #  \param[in] HR_nda_vec HR data as 1D array
    #  \return \f$\ell^2\f$-residual
    def _get_residual_ell2(self, HR_nda_vec):

        My_nda_vec = self._get_M_y()
        MAx_nda_vec = self._MA(HR_nda_vec)

        ## C
        return np.sum((MAx_nda_vec-My_nda_vec)**2)


    ##
    #       Gets the approximate solution via LSMR solver 
    #             (linear least-squares method)
    # \date       2016-08-05 11:31:49+0100
    #
    # \param      self  The object
    # \param      A_fw  Forward operator, function handle
    # \param      A_bw  Backward operator, function handle
    # \param      b     Right-hand side of linear system, 1D array
    #
    # \return     The approximate solution.
    #
    def _get_approximate_solution_lsmr(self, A_fw, A_bw, b, x0=None):

        ## Construct (sparse) linear operator A
        A = LinearOperator((b.size, self._N_voxels_HR_volume), matvec=A_fw, rmatvec=A_bw)

        ## Linear least-squares method: 
        # One (!) test showed that lsqr has lower residual than lsmr in the 
        # end. However, Fong2011 states that "although LSQR and LSMR ultimately
        # converge to similar points, it is safer to use LSMR in situations 
        # where the solver must be terminated early" => Go for that
        x = lsmr(A, b, maxiter=self._iter_max, show=True)[0]

        ## Chop off negative values
        x = np.clip(x, 0, np.inf)

        return x


    ##
    #       Gets the approximate solution via LSQR solver
    #             (linear least-squares method)
    # \date       2016-08-05 11:31:49+0100
    #
    # \param      self  The object
    # \param      A_fw  Forward operator, function handle
    # \param      A_bw  Backward operator, function handle
    # \param      b     Right-hand side of linear system, 1D array
    #
    # \return     The approximate solution.
    #
    def _get_approximate_solution_lsqr(self, A_fw, A_bw, b, x0=None):
        
        ## Construct (sparse) linear operator A
        A = LinearOperator((b.size, self._N_voxels_HR_volume), matvec=A_fw, rmatvec=A_bw)

        ## --- Initial value begin --------------------------------------------
        ## Do not incorporate initial value! It seems to not help in case of
        ## TV-L2! Way faster regardless of all
        ## 
        ## Incorporate initial value for least-squares solver:
        # HR_nda_vec = np.clip(sitk.GetArrayFromImage(self._HR_volume.sitk).flatten(), 0, np.inf)
        # HR_nda_vec = sitk.GetArrayFromImage(self._HR_volume.sitk).flatten()
        # b = b - A_fw(HR_nda_vec)

        ## Linear least-squares method: 
        # One (!) test showed that lsqr has lower residual than lsmr in the 
        # end. However, Fong2011 states that "although LSQR and LSMR ultimately
        # converge to similar points, it is safer to use LSMR in situations 
        # where the solver must be terminated early" => Go for that
        # delta_HR_nda_vec = lsqr(A, b, maxiter=self._iter_max, show=True)[0]

        ## Correct for shift
        # HR_nda_vec += delta_HR_nda_vec
        ## --- Initial value end ----------------------------------------------

        ## Linear least-squares methods: 
        HR_nda_vec = lsqr(A, b, maxiter=self._iter_max, show=True)[0]

        ## Chop off negative values
        x = np.clip(x, 0, np.inf)

        return HR_nda_vec


    ##
    # \brief      Gets the approximate solution via L-BFGS-B solver
    #             (non-linear with bounds).
    # \date       2016-08-05 11:48:20+0100
    #
    # \param      self  The object
    # \param      A_fw  Forward operator, function handle
    # \param      A_bw  Backward operator, function handle
    # \param      b     Right-hand side of linear system, 1D array
    #
    # \return     The approximate solution.
    #
    def _get_approximate_solution_LBFGSB(self, A_fw, A_bw, b, x0=None):
        
        ## Set initial value and bounds
        if x0 is None:
            # x0 = np.clip(sitk.GetArrayFromImage(self._HR_volume.sitk).flatten(), 0, np.inf)
            x0 = np.zeros(np.array(self._HR_volume.sitk.GetSize())[::-1])
        else:
            ## In case initial value is given, the non-masked voxels will
            ## smoothly vary but will not be zero! Hence, prefer zero-init
            x0 = np.clip(x0, 0, np.inf)
        bounds = [[0,None]]*x0.size

        ## Set cost function and its jacobian
        fun = lambda x: 0.5*np.sum((A_fw(x) - b)**2)
        jac = lambda x: A_bw(A_fw(x)-b)

        ## Run solver
        HR_nda_vec = minimize(method='L-BFGS-B', fun=fun, x0=x0, options={'maxiter': self._iter_max, 'disp': True}, jac=jac, bounds=bounds).x

        return HR_nda_vec
        

    ##
    # \brief      Gets the approximate solution via least_squares solver
    #             (non-linear minimization with bounds).
    # \date       2016-08-05 11:48:20+0100
    # \remark     Very slow, also for "smaller" problems such as trachea
    #             reconstructions. Use of no bounds makes it (a bit) faster but
    #             results in insufficient quality of the results
    #
    # \param      self  The object
    # \param      A_fw  Forward operator, function handle
    # \param      A_bw  Backward operator, function handle
    # \param      b     Right-hand side of linear system, 1D array
    #
    # \return     The approximate solution.
    #
    def _get_approximate_solution_least_squares(self, A_fw, A_bw, b, x0=None):

        ## Set initial value and bounds
        x0 = np.clip(sitk.GetArrayFromImage(self._HR_volume.sitk).flatten(), 0, np.inf)
        bounds = (0,np.inf)

        ## Construct (sparse) linear operator A
        A = LinearOperator((b.size, self._N_voxels_HR_volume), matvec=A_fw, rmatvec=A_bw)

        ## Set residual and its Jacobian
        fun = lambda x: A*x - b
        jac =  lambda x: A
        
        ## Run solver
        HR_nda_vec = least_squares(
            fun=fun,
            x0=x0,
            jac=jac,
            jac_sparsity=jac,
            method='trf',
            tr_solver='lsmr',
            bounds=bounds,
            loss="linear",
            # loss="huber", #throws error "operands could not be broadcast together with shapes (315837,) (315837,2)" after applied to trachea example!?
            # loss="soft_l1", #throws error "operands could not be broadcast together with shapes (315837,) (315837,2)" after applied to trachea example!?
            max_nfev=self._iter_max,
            verbose=2
            ).x 

        return HR_nda_vec

    
    ##
    # \brief      Gets the approximate solution via lsq_linear solver
    #             (linear least-squares with bounds).
    # \date       2016-08-05 11:48:20+0100
    # \remark     Does not show any output
    #
    # \param      self  The object
    # \param      A_fw  Forward operator, function handle
    # \param      A_bw  Backward operator, function handle
    # \param      b     Right-hand side of linear system, 1D array
    #
    # \return     The approximate solution.
    #
    def _get_approximate_solution_lsq_linear(self, A_fw, A_bw, b, x0=None):

        ## Construct (sparse) linear operator A
        A = LinearOperator((b.size, self._N_voxels_HR_volume), matvec=A_fw, rmatvec=A_bw)

        ## Run solver
        HR_nda_vec = lsq_linear(A, b, bounds=(0, np.inf), max_iter=self._iter_max, lsq_solver='lsmr', lsmr_tol='auto', verbose=2).x
        # HR_nda_vec = lsq_linear(A, b, max_iter=self._iter_max, lsq_solver=None, lsmr_tol='auto', verbose=2).x
        
        return HR_nda_vec


    ##
    # \brief      Gets the approximate solution via nnls solver
    #             (non-negative linear least-squares).
    # \date       2016-08-05 11:48:20+0100
    # \remark     Does not work with sparse linear operator
    #
    # \param      self  The object
    # \param      A_fw  Forward operator, function handle
    # \param      A_bw  Backward operator, function handle
    # \param      b     Right-hand side of linear system, 1D array
    #
    # \return     The approximate solution.
    #
    def _get_approximate_solution_nnls(self, A_fw, A_bw, b, x0=None):

        ## Construct (sparse) linear operator A
        A = LinearOperator((b.size, self._N_voxels_HR_volume), matvec=A_fw, rmatvec=A_bw)

        ## Run solver:
        HR_nda_vec = nnls(A, b)

        return HR_nda_vec


