##############################################################################
# Copyright (c) 2017,  Met Office, on behalf of HMSO and Queen's Printer
# For further details please refer to the file LICENCE which you
# should have received as part of this distribution.
##############################################################################
#
# Run this make file to generate PSyKAl source in WORKING_DIR from algorithms
# and kernels in SOURCE_DIR. Transformation scripts are sought in
# OPTIMISATION_PATH.
#
# Set the DSL Method in use to collect the correct transformation files.
DSL = psykal
#

# Set default psyclone command additional options
PSYCLONE_PSYKAL_EXTRAS ?= -l all
#

PREPROCESSED_X90_FILES := $(patsubst $(SOURCE_DIR)/%.X90, \
                                     $(WORKING_DIR)/%.x90, \
                                     $(shell find $(SOURCE_DIR) -name '*.X90' -print)) \
                          $(patsubst $(SOURCE_DIR)/%.x90, \
                                     $(WORKING_DIR)/%.x90, \
                                     $(shell find $(SOURCE_DIR) -name '*.x90' -print))

DIRECTORIES := $(patsubst $(SOURCE_DIR)%,$(WORKING_DIR)%, \
                          $(shell find $(SOURCE_DIR) -type d -printf '%p/\n'))
PSYCLONE_CONFIG_FILE ?= $(CORE_ROOT_DIR)/etc/psyclone.cfg
MAKE_THREADS ?= 1

BATCH_PSYCLONE := $(LFRIC_BUILD)/psyclone/batch_psyclone.py

.PHONY: psyclone
psyclone: $(DIRECTORIES) $(PREPROCESSED_X90_FILES)
	$(call MESSAGE,PSyclone - batch processing all files)
	$QPYTHONPATH=$(LFRIC_BUILD)/psyclone:$$PYTHONPATH python $(BATCH_PSYCLONE) \
	           -d $(WORKING_DIR) \
	           --config $(PSYCLONE_CONFIG_FILE) \
	           -j $(MAKE_THREADS) \
	           $(if $(OPTIMISATION_PATH),--optimisation-path $(OPTIMISATION_PATH) --dsl $(DSL)) \
	           $(addprefix --file ,$(PREPROCESSED_X90_FILES)) \
	           $(PSYCLONE_PSYKAL_EXTRAS)

include $(LFRIC_BUILD)/lfric.mk
include $(LFRIC_BUILD)/fortran.mk

MACRO_ARGS := $(addprefix -D,$(PRE_PROCESS_MACROS))

# Where an override file exists in the "psy" directory, delete the PSyclone-
# generated PSy source in favour of the manually provided one.
#
PSY_OVERRIDE_FILES := $(shell find $(SOURCE_DIR)/psy -name '*_psy.f90' 2>/dev/null)
ifneq ($(PSY_OVERRIDE_FILES),)
.PHONY: psyclone_psy_overrides
psyclone_psy_overrides: psyclone
	$(foreach f,$(PSY_OVERRIDE_FILES), \
	  $(eval _stem=$(patsubst $(SOURCE_DIR)/psy/%_psy.f90,%,$(f))) \
	  $(call MESSAGE,Removing,$(_stem)_psy.f90) \
	  $Qrm -f $(WORKING_DIR)/$(_stem)_psy.f90 ;)
endif

.PRECIOUS: $(WORKING_DIR)/%.x90
# Perform preprocessing for big X90 files.
#
ifeq ("$(FORTRAN_COMPILER)", "nvfortran")
$(WORKING_DIR)/%.x90: $(SOURCE_DIR)/%.X90 | $$(dir $$@)
	$(call MESSAGE,Preprocessing, $(subst $(SOURCE_DIR)/,,$<))
	$Q$(FPP) $(FPPFLAGS) $(MACRO_ARGS) -o $@ $<
else
$(WORKING_DIR)/%.x90: $(SOURCE_DIR)/%.X90 | $$(dir $$@)
	$(call MESSAGE,Preprocessing, $(subst $(SOURCE_DIR)/,,$<))
	$Q$(FPP) $(FPPFLAGS) $(MACRO_ARGS) $< $@
endif

# Little x90 files are just copied to the workspace.
#
$(WORKING_DIR)/%.x90: $(SOURCE_DIR)/%.x90 | $$(dir $$@)
	$(call MESSAGE,Copying, $(subst $(SOURCE_DIR)/,,$<))
	$Qcp $< $@

# Create directories in the workspace as needed.
#
$(DIRECTORIES):
	$(call MESSAGE,Creating,$@)
	$Qmkdir -p $@
