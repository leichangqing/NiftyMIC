## \file VolumeReconstruction.py
#  \brief Reconstruct volume given the current position of slices 
# 
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date December 2015


## Import libraries
import os                       # used to execute terminal commands in python
import sys
import itk
import SimpleITK as sitk
import numpy as np
import time                     # 


## Import modules from src-folder
import SimpleITKHelper as sitkh
# import Stack as st
# import Slice as sl


## Class implementing the volume reconstruction given the current position of slices
class VolumeReconstruction:

    ## Constructor
    #  \param stack_manager instance of StackManager containing all stacks and additional information
    def __init__(self, stack_manager):
        self._stack_manager = stack_manager
        self._stacks = stack_manager.get_stacks()
        self._N_stacks = stack_manager.get_number_of_stacks()



    ## Computed reconstructed volume based on current estimated positions of slices
    #  \param[in,out] HR_volume current estimate of reconstructed HR volume (Stack object)
    def update_reconstructed_volume(self, HR_volume):
        print("Update reconstructed volume")

        t0 = time.clock()

        # self._use_discrete_shepard_based_on_Deriche(HR_volume)
        self._use_discrete_shepard(HR_volume)

        time_elapsed = time.clock() - t0
        print("Elapsed time for SDA = %s seconds" %(time_elapsed))

        HR_volume.show()

    ## Recontruct volume based on discrete Shepard's like method, cf. Vercauteren2006, equation (19).
    #  The computation here is based on the YVV variant of Recursive Gaussian Filter and executed
    #  via ITK
    #  \param[in,out] HR_volume current estimate of reconstructed HR volume (Stack object)
    def _use_discrete_shepard(self, HR_volume):
        sigma = 0.7

        shape = sitk.GetArrayFromImage(HR_volume.sitk).shape
        helper_N_nda = np.zeros(shape)
        helper_D_nda = np.zeros(shape)

        default_pixel_value = 0.0

        for i in range(0, self._N_stacks):
        # for i in range(0, 2):
            print("  Stack %s/%s" %(i,self._N_stacks-1))
            stack = self._stacks[i]
            slices = stack.get_slices()
            N_slices = stack.get_number_of_slices()
            
            for j in range(0, N_slices):
                slice = slices[j]

                ## Nearest neighbour resampling of slice to target space (HR volume)
                slice_resampled_sitk = sitk.Resample(
                    slice.sitk, 
                    HR_volume.sitk, 
                    sitk.Euler3DTransform(), 
                    sitk.sitkNearestNeighbor, 
                    default_pixel_value,
                    HR_volume.sitk.GetPixelIDValue())

                ## Extract array of pixel intensities
                nda_slice = sitk.GetArrayFromImage(slice_resampled_sitk)

                ## Look for indices which are stroke by the slice in the isotropic grid
                ind_nonzero = nda_slice>0

                ## update arrays of numerator and denominator
                helper_N_nda[ind_nonzero] += nda_slice[ind_nonzero]
                helper_D_nda[ind_nonzero] += 1
                
                # print("helper_N_nda: (min, max) = (%s, %s)" %(np.min(helper_N_nda), np.max(helper_N_nda)))
                # print("helper_D_nda: (min, max) = (%s, %s)" %(np.min(helper_D_nda), np.max(helper_D_nda)))

        ## Create itk-images with correct header data
        pixel_type = itk.D
        dimension = 3
        image_type = itk.Image[pixel_type, dimension]
        itk2np = itk.PyBuffer[image_type]

        helper_N = itk2np.GetImageFromArray(helper_N_nda) 
        helper_D = itk2np.GetImageFromArray(helper_D_nda) 

        helper_N.SetSpacing(HR_volume.sitk.GetSpacing())
        helper_N.SetDirection(sitkh.get_itk_direction_from_sitk_image(HR_volume.sitk))
        helper_N.SetOrigin(HR_volume.sitk.GetOrigin())

        helper_D.SetSpacing(HR_volume.sitk.GetSpacing())
        helper_D.SetDirection(sitkh.get_itk_direction_from_sitk_image(HR_volume.sitk))
        helper_D.SetOrigin(HR_volume.sitk.GetOrigin())

        ## Apply recursive Gaussian smoothing
        gaussian = itk.SmoothingRecursiveYvvGaussianImageFilter[image_type, image_type].New()
        gaussian.SetSigma(sigma)
        gaussian.SetInput(helper_N)
        gaussian.Update()
        HR_volume_update_N = gaussian.GetOutput()
        nda_N = itk2np.GetArrayFromImage(HR_volume_update_N)

        gaussian = itk.SmoothingRecursiveYvvGaussianImageFilter[image_type, image_type].New()
        gaussian.SetSigma(sigma)
        gaussian.SetInput(helper_D)
        gaussian.Update()
        HR_volume_update_D = gaussian.GetOutput()
        nda_D = itk2np.GetArrayFromImage(HR_volume_update_D)

        ## Compute data array of HR volume:
        # nda_D[nda_D==0]=1 
        # nda = nda_N/nda_D.astype(float)
        nda = nda_N/nda_D
        # HR_volume_update.CopyInformation(HR_volume.sitk)

        ## Update HR volume image file within Stack-object HR_volume
        # nda = itk2np.GetArrayFromImage(HR_volume_update)
        HR_volume_update = sitk.GetImageFromArray(nda)
        HR_volume_update.CopyInformation(HR_volume.sitk)

        HR_volume.sitk = HR_volume_update

        return None


    ## Recontruct volume based on discrete Shepard's like method, cf. Vercauteren2006, equation (19).
    #  TODO: Delete at some point when not used anymore
    #  The computation here is based on the Deriche variant of Recursive Gaussian Filter and executed
    #  via SimpleITK
    #  \param[in,out] HR_volume current estimate of reconstructed HR volume (Stack object)
    def _use_discrete_shepard_based_on_Deriche(self, HR_volume):
        sigma = 1

        shape = sitk.GetArrayFromImage(HR_volume.sitk).shape
        helper_N_nda = np.zeros(shape)
        helper_D_nda = np.zeros(shape)

        default_pixel_value = 0.0

        for i in range(0, self._N_stacks):
        # for i in range(0, 2):
            print("  Stack %s/%s" %(i,self._N_stacks-1))
            stack = self._stacks[i]
            slices = stack.get_slices()
            N_slices = stack.get_number_of_slices()
            
            for j in range(0, N_slices):
                slice = slices[j]

                ## Nearest neighbour resampling of slice to target space (HR volume)
                slice_resampled_sitk = sitk.Resample(
                    slice.sitk, 
                    HR_volume.sitk, 
                    sitk.Euler3DTransform(), 
                    sitk.sitkNearestNeighbor, 
                    default_pixel_value,
                    HR_volume.sitk.GetPixelIDValue())

                ## Extract array of pixel intensities
                nda_slice = sitk.GetArrayFromImage(slice_resampled_sitk)

                ## Look for indices which are stroke by the slice in the isotropic grid
                ind_nonzero = nda_slice>0

                ## update arrays of numerator and denominator
                helper_N_nda[ind_nonzero] += nda_slice[ind_nonzero]
                helper_D_nda[ind_nonzero] += 1
                
                # print("helper_N_nda: (min, max) = (%s, %s)" %(np.min(helper_N_nda), np.max(helper_N_nda)))
                # print("helper_D_nda: (min, max) = (%s, %s)" %(np.min(helper_D_nda), np.max(helper_D_nda)))


        ## Create sitk-images with correct header data
        helper_N = sitk.GetImageFromArray(helper_N_nda) 
        helper_D = sitk.GetImageFromArray(helper_D_nda) 

        helper_N.CopyInformation(HR_volume.sitk)
        helper_D.CopyInformation(HR_volume.sitk)

        ## Apply recursive Gaussian smoothing
        gaussian = sitk.SmoothingRecursiveGaussianImageFilter()
        gaussian.SetSigma(sigma)

        HR_volume_update_N = gaussian.Execute(helper_N)
        HR_volume_update_D = gaussian.Execute(helper_D)

        ## Avoid undefined division by zero
        """
        HACK start
        """
        ## HACK for denominator
        nda = sitk.GetArrayFromImage(HR_volume_update_D)
        ind_min = np.unravel_index(np.argmin(nda), nda.shape)
        # print nda[nda<0]
        # print nda[ind_min]

        eps = 1e-8
        nda[nda<=eps]=1   # actually only nda=0 but some are negative!?
        print("denominator min = %s" % np.min(nda))


        HR_volume_update_D = sitk.GetImageFromArray(nda)
        HR_volume_update_D.CopyInformation(HR_volume.sitk)

        ## HACK for numerator given that some intensities are negative!?
        nda = sitk.GetArrayFromImage(HR_volume_update_N)
        ind_min = np.unravel_index(np.argmin(nda), nda.shape)
        nda[nda<=eps]=0
        # print nda[nda<0]
        print("numerator min = %s" % np.min(nda))
        """
        HACK end
        """
        
        ## Compute HR volume based on scattered data approximation with correct header (might be redundant):
        HR_volume_update = HR_volume_update_N/HR_volume_update_D
        HR_volume_update.CopyInformation(HR_volume.sitk)

        ## Update HR volume image file within Stack-object HR_volume
        HR_volume.sitk = HR_volume_update


        ##
        nda = sitk.GetArrayFromImage(HR_volume_update)
        print np.min(nda)


        return None