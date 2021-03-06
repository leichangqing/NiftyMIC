# Motion Correction and Volumetric Image Reconstruction of 2D Ultra-fast MRI

NiftyMIC is a Python-based open-source toolkit for research developed within the [GIFT-Surg][giftsurg] project to reconstruct an isotropic, high-resolution volume from multiple, possibly motion-corrupted, stacks of low-resolution 2D slices. The framework relies on slice-to-volume registration algorithms for motion correction and reconstruction-based Super-Resolution (SR) techniques for the volumetric reconstruction. 
Please note that currently **only Python 2** is supported.

The algorithm and software were developed by [Michael Ebner][mebner] at the [Translational Imaging Group][tig] in the [Centre for Medical Image Computing][cmic] at [University College London (UCL)][ucl].

If you have any questions or comments, please drop an email to `michael.ebner.14@ucl.ac.uk`.

## Features
Several methods have been implemented to solve the **Super-Resolution Reconstruction** (SRR) problem
<!-- ```math -->
<!-- \vec{x}^* := \text{argmin}_{\vec{x}} \Big[\sum_{k=1}^K \sum_{i=1}^{N_k} \varrho\big( (A_k\vec{x} - \vec{y}_k)_i^2 \big) + \alpha\,\text{Reg}(\vec{x}) \Big] -->
<!-- ``` -->
<p align="center">
<img src="http://latex.codecogs.com/svg.latex?%5Cvec%7Bx%7D%5E%2A%3A%3D%5Ctext%7Bargmin%7D_%7B%5Cvec%7Bx%7D%7D%5CBig%5B%5Csum_%7Bk%3D1%7D%5EK%5Csum_%7Bi%3D1%7D%5E%7BN_k%7D%5Cvarrho%5Cbig%28%28A_k%5Cvec%7Bx%7D-%5Cvec%7By%7D_k%29_i%5E2%5Cbig%29%2B%5Calpha%5C%2C%5Ctext%7BReg%7D%28%5Cvec%7Bx%7D%29%5CBig%5D">
</p>

<!--to obtain the (vectorized) high-resolution 3D MRI volume $`\vec{x}\in\mathbb{R}^N`$ from multiple, possibly motion corrupted, low-resolution stacks of (vectorized) 2D MR slices $`\vec{y}_k \in\mathbb{R}^{N_k}`$ with $`N_k\ll N`$ for $`k=1,...,\,K`$-->
<!--for a variety of regularizers $`\text{Reg}`$ and data loss functions $`\varrho`$.-->
<!--The linear operator $`A_k := D_k B_k W_k`$ represents the comd operator descri the (rigid) motion $`W_k`$, the blurring operator $`B_k`$ and the downsampling operator $`D_k`$.-->
to obtain the (vectorized) high-resolution 3D MRI volume ![img](http://latex.codecogs.com/svg.latex?%5Cvec%7Bx%7D%5Cin%5Cmathbb%7BR%7D%5EN) from multiple, possibly motion corrupted, low-resolution stacks of (vectorized) 2D MR slices ![img](http://latex.codecogs.com/svg.latex?%5Cvec%7By%7D_k%5Cin%5Cmathbb%7BR%7D%5E%7BN_k%7D) with ![img](http://latex.codecogs.com/svg.latex?N_k%5Cll%7BN%7D) for ![img](http://latex.codecogs.com/svg.latex?k%3D1%2C...%2C%5C%2CK)
for a variety of regularizers ![img](http://latex.codecogs.com/svg.latex?%5Ctext%7BReg%7D) and data loss functions ![img](http://latex.codecogs.com/svg.latex?%5Cvarrho).
The linear operator ![img](http://latex.codecogs.com/svg.latex?A_k%3A%3DD_kB_kW_k) represents the combined operator describing the (rigid) motion ![img](http://latex.codecogs.com/svg.latex?W_k), the blurring operator ![img](http://latex.codecogs.com/svg.latex?B_k) and the downsampling operator ![img](http://latex.codecogs.com/svg.latex?D_k).

---

The provided **data loss functions** ![img](http://latex.codecogs.com/svg.latex?%5Cvarrho) are motivated by [SciPy](https://docs.scipy.org/doc/scipy-0.19.0/reference/generated/scipy.optimize.least_squares.html) and allow for robust outlier rejection. Implemented data loss functions are:
<!--$`\varrho(e)=e`$-->
<!--$`\varrho(e)=2(\sqrt{1+e}-1)`$ -->
<!--$`\varrho(e)=|e|_\gamma=\begin{cases}e,&e<\gamma^2\\2\gamma\sqrt{e}-\gamma^2,&e\ge\gamma^2\end{cases}`$-->
<!--$`\varrho(e)=\arctan(e)`$-->
<!--$`\varrho(e)=\ln(1 + e)`$-->
* `linear`: ![img](http://latex.codecogs.com/svg.latex?%5Cvarrho%28e%29%3De)
* `soft_l1`: ![img](http://latex.codecogs.com/svg.latex?%5Cvarrho%28e%29%3D2%28%5Csqrt%7B1%2Be%7D-1%29)
* `huber`: ![img](http://latex.codecogs.com/svg.latex?%5Cvarrho%28e%29%3D%7Ce%7C_%5Cgamma%3D%5Cbegin%7Bcases%7De%2C%26e%3C%5Cgamma%5E2%5C%5C2%5Cgamma%5Csqrt%7Be%7D-%5Cgamma%5E2%2C%26e%5Cge%5Cgamma%5E2%5Cend%7Bcases%7D)
* `arctan`: ![img](http://latex.codecogs.com/svg.latex?%5Cvarrho%28e%29%3D%5Carctan%28e%29)
* `cauchy`: ![img](http://latex.codecogs.com/svg.latex?%5Cvarrho%28e%29%3D%5Cln%281%2Be%29)

---

The **available regularizers** include
<!-- * Zeroth-order Tikhonov (TK0): $`\text{Reg}(\vec{x}) = \frac{1}{2}\Vert \vec{x} \Vert_{\ell^2}^2`$ -->
<!-- * First-order Tikhonov (TK1): $`\text{Reg}(\vec{x}) = \frac{1}{2}\Vert \nabla \vec{x} \Vert_{\ell^2}^2`$ -->
<!-- * Isotropic Total Variation (TV): $`\text{Reg}(\vec{x}) = \text{TV}_\text{iso}(\vec{x}) = \big\Vert |\nabla \vec{x}| \big\Vert_{\ell^1}`$ -->
<!-- * Huber Function: $`\text{Reg}(\vec{x}) = \frac{1}{2\gamma} \big| |\nabla \vec{x}| \big|_{\gamma}`$ -->
* Zeroth-order Tikhonov (TK0): ![img](http://latex.codecogs.com/svg.latex?%5Ctext%7BReg%7D%28%5Cvec%7Bx%7D%29%3D%5Cfrac%7B1%7D%7B2%7D%5CVert%5Cvec%7Bx%7D%5CVert_%7B%5Cell%5E2%7D%5E2)
* First-order Tikhonov (TK1): ![img](http://latex.codecogs.com/svg.latex?%5Ctext%7BReg%7D%28%5Cvec%7Bx%7D%29%3D%5Cfrac%7B1%7D%7B2%7D%5CVert%5Cnabla%5Cvec%7Bx%7D%5CVert_%7B%5Cell%5E2%7D%5E2)
* Isotropic Total Variation (TV): ![img](http://latex.codecogs.com/svg.latex?%5Ctext%7BReg%7D%28%5Cvec%7Bx%7D%29%3D%5Ctext%7BTV%7D_%5Ctext%7Biso%7D%28%5Cvec%7Bx%7D%29%3D%5Cbig%5CVert%7C%5Cnabla%5Cvec%7Bx%7D%7C%5Cbig%5CVert_%7B%5Cell%5E1%7D)
* Huber Function: ![img](http://latex.codecogs.com/svg.latex?%5Ctext%7BReg%7D%28%5Cvec%7Bx%7D%29%3D%5Cfrac%7B1%7D%7B2%5Cgamma%7D%5Cbig%7C%7C%5Cnabla%5Cvec%7Bx%7D%7C%5Cbig%7C_%7B%5Cgamma%7D)

---

Additionally, the choice of finding **optimal reconstruction parameters** is facilitated by the [Numerical Solver Library (NSoL)][nsol].


## Disclaimer
NiftyMIC supports medical image registration and volumetric reconstruction for ultra-fast 2D MRI. It has not been tested on larger cohort data yet.
**NiftyMIC is not intended for clinical use**.

## How to cite
If you use this software in your work, please cite [Ebner et al., 2018][citation].

* Ebner, M., Chung, K. K., Prados, F., Cardoso, M. J., Chard, D. T., Vercauteren, T., & Ourselin, S. (2018). Volumetric reconstruction from printed films: Enabling 30 year longitudinal analysis in MR neuroimaging. NeuroImage, 165, 238–250.


## Installation

NiftyMIC is currently supported for **Python 2 only** and was tested on

* Mac OS X 10.10 and 10.12
* Ubuntu 14.04 and 16.04

NiftyMIC builds on a couple of additional libraries developed within the [GIFT-Surg][giftsurg] project including 
* [NSoL][nsol]
* [SimpleReg][simplereg]
* [PySiTK][pysitk]
* [ITK_NiftyMIC][itkniftymic]

whose installation requirements need to be met. Therefore, the installation comes in three steps:

1. [Installation of ITK_NiftyMIC][itkniftymic]
1. [Installation of SimpleReg dependencies][simplereg-dependencies]
1. [Installation of NiftyMIC][niftymic-install]


## Usage

Provided the input MR image data in NIfTI format (`nii` or `nii.gz`), NiftyMIC can reconstruct an isotropic, high-resolution volume from multiple, possibly motion-corrupted, stacks of low-resolution 2D slices.

### Volumetric MR Reconstruction from Motion Corrupted 2D Slices
Leveraging a two-step registration-reconstruction approach an isotropic, high-resolution 3D volume can be generated from multiple stacks of low-resolution slices.

Examples for basic usage are:
```
niftymic_reconstruct_volume \
--dir-input dir-with-multiple-stacks \
--dir-output output-dir \
--suffix-mask _mask
```
```
niftymic_reconstruct_volume \
--filenames path-to-stack1.nii.gz ... path-to-stackN.nii.gz \
--dir-output output-dir \
--suffix-mask _mask
```

The obtained motion-correction transformations can be stored for further processing, e.g. by using `niftymic_reconstruct_volume_from_slices.py` to solve the SRR problem for a variety of different regularization and data loss function types.

### SRR Methods for Motion Corrected (or Static) Data

After performed motion correction (or having static data in the first place),

1. different solvers and regularizers can be used to solve the SRR problem for comparison, and
1. parameter studies can be performed to find optimal reconstruction parameters.

#### 1. SRR from Motion Corrected (or Static) Slice Acquisitions
Solve the SRR problem for motion corrected data:
```
niftymic_reconstruct_volume_from_slices \
--dir-input dir-to-motion-correction \
--dir-output output-dir \
--reconstruction-type HuberL2 \
--alpha 0.003
```
```
niftymic_reconstruct_volume_from_slices \
--dir-input dir-to-motion-correction \
--dir-output output-dir \
--reconstruction-type TK1L2 \
--alpha 0.03
```

Solve the SRR problem for static data:
```
niftymic_reconstruct_volume_from_slices \
--filenames path-to-stack1.nii.gz ... path-to-stackN.nii.gz \
--dir-output output-dir \
--reconstruction-type HuberL2 \
--alpha 0.003 
--suffix-mask _mask
```
```
niftymic_reconstruct_volume_from_slices \
--filenames path-to-stack1.nii.gz ... path-to-stackN.nii.gz \
--dir-output output-dir \
--reconstruction-type TK1L2 \
--alpha 0.03 \
--suffix-mask _mask
```

#### 2. Parameter Studies to Determine Optimal SRR Parameters
The optimal choice for reconstruction parameters like the regularization parameter or data loss function can be found by running parameter studies. This includes L-curve studies and direct comparison against a reference volume for various cost functions.

Example are:
```
niftymic_run_reconstruction_parameter_study \
--dir-input dir-to-motion-correction \
--dir-output dir-to-param-study-output \
--reconstruction-type HuberL2 \
--reference path-to-reference-volume.nii.gz \
--reference-mask path-to-reference-volume_mask.nii.gz \
--measures RMSE PSNR NCC NMI SSIM \
--alpha-range 0.001 0.003 10
```
```
niftymic_run_reconstruction_parameter_study \
--dir-input dir-to-motion-correction \
--dir-output dir-to-param-study-output \
--reconstruction-type TVL2 \
--reference path-to-reference-volume.nii.gz \
--reference-mask path-to-reference-volume_mask.nii.gz \
--measures RMSE PSNR NCC NMI SSIM \
--alpha-range 0.001 0.003 10
```
```
niftymic_run_reconstruction_parameter_study \
--dir-input dir-to-motion-correction \
--dir-output dir-to-param-study-output \
--reconstruction-type TK1L2 \
--reference path-to-reference-volume.nii.gz \
--reference-mask path-to-reference-volume_mask.nii.gz \
--measures RMSE PSNR NCC NMI SSIM \
--alpha-range 0.001 0.05 20
```

The results can be assessed by accessing the [NSoL][nsol]-script `show_parameter_study.py` via
```
niftymic_show_parameter_study \
--dir-input dir-to-param-study-output \
--study-name TK1L2 \
--dir-output-figures dir-to-figures
```

## Licensing and Copyright
Copyright (c) 2017, [University College London][ucl].
This framework is made available as free open-source software under the [BSD-3-Clause License][bsd]. Other licenses may apply for dependencies.


## Funding
This work is partially funded by the UCL [Engineering and Physical Sciences Research Council (EPSRC)][epsrc] Centre for Doctoral Training in Medical Imaging (EP/L016478/1), the Innovative Engineering for Health award ([Wellcome Trust][wellcometrust] [WT101957] and [EPSRC][epsrc] [NS/A000027/1]), and supported by researchers at the [National Institute for Health Research][nihr] [University College London Hospitals (UCLH)][uclh] Biomedical Research Centre.

## References
Associated publications are 
* [[Ebner2018]][citation] Ebner, M., Chung, K. K., Prados, F., Cardoso, M. J., Chard, D. T., Vercauteren, T., & Ourselin, S. (2018). Volumetric reconstruction from printed films: Enabling 30 year longitudinal analysis in MR neuroimaging. NeuroImage, 165, 238–250.
* [[Ranzini2017]](https://mski2017.files.wordpress.com/2017/09/miccai-mski2017.pdf) Ranzini, M. B., Ebner, M., Cardoso, M. J., Fotiadou, A., Vercauteren, T., Henckel, J., Hart, A., Ourselin, S., and Modat, M. (2017). Joint Multimodal Segmentation of Clinical CT and MR from Hip Arthroplasty Patients. MICCAI Workshop on Computational Methods and Clinical Applications in Musculoskeletal Imaging (MSKI) 2017.
* [[Ebner2017]](https://link.springer.com/chapter/10.1007%2F978-3-319-52280-7_1) Ebner, M., Chouhan, M., Patel, P. A., Atkinson, D., Amin, Z., Read, S., Punwani, S., Taylor, S., Vercauteren, T., and Ourselin, S. (2017). Point-Spread-Function-Aware Slice-to-Volume Registration: Application to Upper Abdominal MRI Super-Resolution. In Zuluaga, M. A., Bhatia, K., Kainz, B., Moghari, M. H., and Pace, D. F., editors, Reconstruction, Segmentation, and Analysis of Medical Images. RAMBO 2016, volume 10129 of Lecture Notes in Computer Science, pages 3–13. Springer International Publishing.

[citation]: https://www.sciencedirect.com/science/article/pii/S1053811917308042
[mebner]: http://cmictig.cs.ucl.ac.uk/people/phd-students/michael-ebner
[tig]: http://cmictig.cs.ucl.ac.uk
[bsd]: https://opensource.org/licenses/BSD-3-Clause
[giftsurg]: http://www.gift-surg.ac.uk
[cmic]: http://cmic.cs.ucl.ac.uk
[guarantors]: https://guarantorsofbrain.org/
[ucl]: http://www.ucl.ac.uk
[uclh]: http://www.uclh.nhs.uk
[epsrc]: http://www.epsrc.ac.uk
[wellcometrust]: http://www.wellcome.ac.uk
[mssociety]: https://www.mssociety.org.uk/
[nihr]: http://www.nihr.ac.uk/research
[itkniftymic]: https://github.com/gift-surg/ITK_NiftyMIC/wikis/home
[niftymic-install]: https://github.com/gift-surg/NiftyMIC/wikis/niftymic-installation
[nsol]: https://github.com/gift-surg/NSoL
[simplereg]: https://github.com/gift-surg/SimpleReg
[simplereg-dependencies]: https://github.com/gift-surg/SimpleReg/wikis/simplereg-dependencies
[pysitk]: https://github.com/gift-surg/PySiTK
