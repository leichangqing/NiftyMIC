##
# \file DataReader.py
# \brief      Reads data and returns Stack objects
#
# \author     Michael Ebner (michael.ebner.14@ucl.ac.uk)
# \date       July 2017
#


import SimpleITK as sitk
import natsort
import numpy as np
import os
import re
# Import libraries
from abc import ABCMeta, abstractmethod

import niftymic.base.stack as st
import pysitk.python_helper as ph
import pysitk.simple_itk_helper as sitkh
import niftymic.base.exceptions as exceptions
from niftymic.definitions import ALLOWED_EXTENSIONS
from niftymic.definitions import REGEX_FILENAMES
from niftymic.definitions import REGEX_FILENAME_EXTENSIONS

##
# DataReader is an abstract class to read data.
# \date       2017-07-12 11:38:07+0100
#


class DataReader(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def read_data(self):
        pass

    @abstractmethod
    def get_data(self):
        pass


##
# DataReader is an abstract class to read 3D images.
# \date       2017-07-12 11:38:07+0100
#
class ImageDataReader(DataReader):
    __metaclass__ = ABCMeta

    def __init__(self):
        DataReader.__init__(self)
        self._stacks = None

    ##
    # Returns the read data as list of Stack objects
    # \date       2017-07-12 11:38:52+0100
    #
    # \param      self  The object
    #
    # \return     The stacks.
    #
    def get_data(self):

        if type(self._stacks) is not list:
            raise exceptions.ObjectNotCreated("read_data")

        return self._stacks


##
# ImageDirectoryReader reads images and their masks from a given directory and
# returns them as a list of Stack objects.
# \date       2017-07-12 11:36:22+0100
#
class ImageDirectoryReader(ImageDataReader):

    ##
    # Store relevant information to images and their potential masks from a
    # specified directory
    # \date       2017-07-11 19:04:25+0100
    #
    # \param      self               The object
    # \param      path_to_directory  String to specify the path to input
    #                                directory.
    # \param      suffix_mask        extension of stack filename as string
    #                                indicating associated mask, e.g. "_mask"
    #                                for "A_mask.nii".
    # \param      extract_slices     Boolean to indicate whether given 3D image
    #                                shall be split into its slices along the
    #                                k-direction.
    #
    def __init__(self,
                 path_to_directory,
                 suffix_mask="_mask",
                 extract_slices=True):

        super(self.__class__, self).__init__()

        self._path_to_directory = path_to_directory
        self._suffix_mask = suffix_mask
        self._extract_slices = extract_slices

    ##
    # Reads the image data from the given folder.
    # \date       2017-07-11 17:10:40+0100
    #
    def read_data(self):

        if not ph.directory_exists(self._path_to_directory):
            raise exceptions.DirectoryNotExistent(self._path_to_directory)

        abs_path_to_directory = os.path.abspath(self._path_to_directory)

        # Get data filenames of images without filename extension
        pattern = "(" + REGEX_FILENAMES + ")[.]" + REGEX_FILENAME_EXTENSIONS
        pattern_mask = "(" + REGEX_FILENAMES + ")" + self._suffix_mask + \
            "[.]" + REGEX_FILENAME_EXTENSIONS
        p = re.compile(pattern)
        p_mask = re.compile(pattern_mask)

        # Exclude potential mask filenames
        # TODO: If folder contains A.nii and A.nii.gz that ambiguity will not
        #       be detected
        dic_filenames = {p.match(f).group(1): p.match(f).group(0)
                         for f in os.listdir(abs_path_to_directory)
                         if p.match(f) and not p_mask.match(f)}

        dic_filenames_mask = {p_mask.match(f).group(1):
                              p_mask.match(f).group(0)
                              for f in os.listdir(abs_path_to_directory)
                              if p_mask.match(f)}

        # Filenames without filename ending as sorted list
        filenames = natsort.natsorted(
            dic_filenames.keys(), key=lambda y: y.lower())

        self._stacks = [None] * len(filenames)
        for i, filename in enumerate(filenames):

            abs_path_image = os.path.join(abs_path_to_directory,
                                          dic_filenames[filename])

            if filename in dic_filenames_mask.keys():
                abs_path_mask = os.path.join(abs_path_to_directory,
                                             dic_filenames_mask[filename])
            else:
                ph.print_info("No mask found for '%s'." %
                              (abs_path_image))
                abs_path_mask = None

            self._stacks[i] = st.Stack.from_filename(
                abs_path_image,
                abs_path_mask,
                extract_slices=self._extract_slices)


##
# MultipleImagesReader reads multiple nifti images and returns them as a list
# of Stack objects.
# \date       2017-07-12 11:28:10+0100
#
class MultipleImagesReader(ImageDataReader):

    ##
    # Store relevant information to read multiple images and their potential
    # masks.
    # \date       2017-07-11 19:04:25+0100
    #
    # \param      self            The object
    # \param      file_paths      The paths to filenames as list of strings,
    #                             e.g. ["A.nii.gz", "B.nii", "C.nii.gz"]
    # \param      suffix_mask     extension of stack filename as string
    #                             indicating associated mask, e.g. "_mask" for
    #                             "A_mask.nii".
    # \param      extract_slices  Boolean to indicate whether given 3D image
    #                             shall be split into its slices along the
    #                             k-direction.
    #
    def __init__(self, file_paths, suffix_mask="_mask", extract_slices=True):

        super(self.__class__, self).__init__()

        # Get list of paths to image
        self._file_paths = file_paths
        self._suffix_mask = suffix_mask
        self._extract_slices = extract_slices

    ##
    # Reads the data of multiple images.
    # \date       2017-07-12 11:30:35+0100
    #
    def read_data(self):

        self._stacks = [None] * len(self._file_paths)

        for i, file_path in enumerate(self._file_paths):

            # Build absolute path to directory of image
            path_to_directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)

            if not ph.directory_exists(path_to_directory):
                raise exceptions.DirectoryNotExistent(path_to_directory)
            abs_path_to_directory = os.path.abspath(path_to_directory)

            # Get absolute path mask to image
            pattern = "(" + REGEX_FILENAMES + \
                ")[.]" + REGEX_FILENAME_EXTENSIONS
            p = re.compile(pattern)
            # filename = [p.match(f).group(1) if p.match(file_path)][0]
            if not file_path.endswith(tuple(ALLOWED_EXTENSIONS)):
                raise IOError("Input image type not correct. Allowed types %s"
                              % "(" + (", or ").join(ALLOWED_EXTENSIONS) + ")")

            # Strip extension from filename to find associated mask
            filename = [re.sub("." + ext, "", filename)
                        for ext in ALLOWED_EXTENSIONS
                        if file_path.endswith(ext)][0]
            pattern_mask = filename + self._suffix_mask + "[.]" + \
                REGEX_FILENAME_EXTENSIONS
            p_mask = re.compile(pattern_mask)
            filename_mask = [p_mask.match(f).group(0)
                             for f in os.listdir(abs_path_to_directory)
                             if p_mask.match(f)]

            if len(filename_mask) == 0:
                abs_path_mask = None
            else:
                abs_path_mask = os.path.join(abs_path_to_directory,
                                             filename_mask[0])
            self._stacks[i] = st.Stack.from_filename(
                file_path,
                abs_path_mask,
                extract_slices=self._extract_slices)


##
# ImageSlicesDirectoryReader reads multiple stacks and their associated
# individual slices from a directory.
# Rationale: Read individual slices after performed slice-to-volume
# registration steps.
# \date       2017-07-17 22:32:11+0100
#
class ImageSlicesDirectoryReader(ImageDataReader):

    ##
    # Store relevant information to images, slices and their potential masks
    # from a specified directory
    # \date       2017-07-17 22:32:01+0100
    #
    # \param      self               The object
    # \param      path_to_directory  String to specify the path to input
    #                                directory where images and associated
    #                                slices are stored.
    # \param      suffix_mask        extension of stack filename as string
    #                                indicating associated mask, e.g. "_mask"
    #                                for "A_mask.nii".
    #
    def __init__(self,
                 path_to_directory,
                 image_selection=None,
                 suffix_mask="_mask",
                 prefix_slice="_slice"):

        super(self.__class__, self).__init__()

        self._path_to_directory = path_to_directory
        self._suffix_mask = suffix_mask
        self._prefix_slice = prefix_slice
        self._image_selection = image_selection
        self._transforms_sitk = None

    def read_data(self):

        if not ph.directory_exists(self._path_to_directory):
            raise exceptions.DirectoryNotExistent(self._path_to_directory)

        abs_path_to_directory = os.path.abspath(self._path_to_directory)

        # Get data filenames of images by finding the prefixes associated
        # to the slices which are build as filename_slice[0-9]+.nii.gz
        pattern = "(" + REGEX_FILENAMES + ")" + \
            self._prefix_slice + "[0-9]+[.]" + REGEX_FILENAME_EXTENSIONS

        p = re.compile(pattern)

        dic_filenames = {
            p.match(f).group(1): p.match(f).group(0)
            for f in os.listdir(abs_path_to_directory) if p.match(f)
        }

        # Filenames without filename ending as sorted list
        filenames = natsort.natsorted(
            dic_filenames.keys(), key=lambda y: y.lower())

        # Reduce filenames to be read to selection only
        if self._image_selection is not None:
            filenames = [f for f in self._image_selection if f in filenames]

        self._stacks = [None] * len(filenames)
        self._slice_transforms_sitk = [None] * len(filenames)
        for i, filename in enumerate(filenames):

            # Get slice names associated to stack
            pattern = "(" + filenames[i] + self._prefix_slice + \
                ")([0-9]+)[.]" + REGEX_FILENAME_EXTENSIONS
            p = re.compile(pattern)

            # Dictionary linking slice number with filename (without extension)
            dic_slice_filenames = {
                int(p.match(f).group(2)): p.match(f).group(1) + p.match(f).group(2)
                for f in os.listdir(abs_path_to_directory) if p.match(f)
            }

            # Build stack from image and its found slices
            self._stacks[i] = st.Stack.from_slice_filenames(
                dir_input=self._path_to_directory,
                prefix_stack=filename,
                suffix_mask=self._suffix_mask,
                dic_slice_filenames=dic_slice_filenames)

            # Read
            self._slice_transforms_sitk[i] = [
                sitk.ReadTransform(os.path.join(
                    self._path_to_directory,
                    "%s.tfm" % dic_slice_filenames[k]))
                for k in sorted(dic_slice_filenames.keys())
            ]

    ##
    # Gets the transforms associated with each individual slice for all stacks.
    # \date       2017-09-20 01:20:30+0100
    #
    # \param      self  The object
    #
    # \return     List of slice transform lists. Each transform is of type
    #             sitk.Transform
    #
    def get_slice_transforms_sitk(self):
        return self._slice_transforms_sitk


##
# MultiComponentImageReader reads a single image which has multiple components
# \date       2017-08-05 23:39:24+0100
#
class MultiComponentImageReader(ImageDataReader):

    def __init__(self, path_to_image, path_to_image_mask=None):

        super(self.__class__, self).__init__()

        self._path_to_image = path_to_image
        self._path_to_image_mask = path_to_image_mask

    def read_data(self):
        vector_image_sitk = sitkh.read_sitk_vector_image(
            self._path_to_image,
            dtype=np.float64)

        if self._path_to_image_mask is not None:
            vector_image_sitk_mask = sitkh.read_sitk_vector_image(
                self._path_to_image_mask,
                dtype=np.uint8,
            )

        N_components = vector_image_sitk.GetNumberOfComponentsPerPixel()

        self._stacks = [None] * N_components

        filename_base = os.path.basename(self._path_to_image).split(".")[0]
        for i in range(N_components):
            image_sitk = sitk.VectorIndexSelectionCast(
                vector_image_sitk, i)
            if self._path_to_image_mask is not None:
                image_sitk_mask = sitk.VectorIndexSelectionCast(
                    vector_image_sitk_mask, i)
            else:
                image_sitk_mask = None

            filename = filename_base + "_" + str(i)
            self._stacks[i] = st.Stack.from_sitk_image(
                image_sitk=image_sitk,
                filename=filename,
                image_sitk_mask=image_sitk_mask)


class TransformationDataReader(DataReader):
    __metaclass__ = ABCMeta

    def __init__(self):
        DataReader.__init__(self)
        self._transforms_sitk = None

    def get_data(self):
        return self._transforms_sitk


class TransformationDirectoryReader(TransformationDataReader):

    def __init__(self, directory):
        TransformationDataReader.__init__(self)
        self._directory = directory

    def read_data(self, extension="tfm"):
        pattern = REGEX_FILENAMES + "[.]" + extension
        p = re.compile(pattern)

        filenames = [
            os.path.join(self._directory, f)
            for f in os.listdir(self._directory) if p.match(f)
        ]
        filenames = natsort.natsorted(filenames, key=lambda y: y.lower())

        transforms_reader = MultipleTransformationsReader(filenames)
        transforms_reader.read_data()
        self._transforms_sitk = transforms_reader.get_data()


class MultipleTransformationsReader(TransformationDataReader):

    def __init__(self, file_paths):
        super(self.__class__, self).__init__()
        self._file_paths = file_paths

        # Third line in *.tfm file contains information on the transform type
        self._transform_type = {
            "Euler3DTransform_double_3_3": sitk.Euler3DTransform,
            "AffineTransform_double_3_3": sitk.AffineTransform,
        }

    def read_data(self):
        self._transforms_sitk = [None] * len(self._file_paths)

        for i in range(len(self._file_paths)):
            # Read transform as type sitk.Transform
            transform_sitk = sitk.ReadTransform(self._file_paths[i])

            # Convert transform to respective type, e.g. Euler, Affine etc
            transform_type = open(self._file_paths[i]).readlines()[2]
            transform_type = re.sub("\n", "", transform_type)
            transform_type = transform_type.split(" ")[1]
            self._transforms_sitk[i] = self._transform_type[transform_type](
                transform_sitk)
