You can build and deploy your own customized Ubuntu images using [Packer](https://developer.hashicorp.com/packer).

Canonical maintains a central repository of templates and instructions that cover Ubuntu and many other operating systems:

[Packer MAAS templates on GitHub](https://github.com/canonical/packer-maas)

The README in that repository explains:

- How to install Packer and dependencies
- Hardware requirements
- How to build images for Ubuntu and non-Ubuntu systems
- How to upload and test images in MAAS
- Debugging tips and project structure for contributing

If you only need Ubuntu images, start in the `ubuntu/` directory of the repository.
That folder provides a ready-made template and `Makefile` for building Ubuntu images.

For more background, see:
- [Packer documentation](https://developer.hashicorp.com/packer/docs)
