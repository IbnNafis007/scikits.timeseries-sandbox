"""A special directive for including a matplotlib plot.

Given a path to a .py file, it includes the source code inline, then:

- On HTML, will include a .png with a link to a high-res .png.

- On LaTeX, will include a .pdf

This directive supports all of the options of the `image` directive,
except for `target` (since plot will add its own target).

Additionally, if the :include-source: option is provided, the literal
source will be included inline, as well as a link to the source.
"""

import sys, os, glob, shutil, code, imp
from docutils.parsers.rst import directives

import matplotlib
import matplotlib.pyplot as plt

try:
    # docutils 0.4
    from docutils.parsers.rst.directives.images import align
except ImportError:
    # docutils 0.5
    from docutils.parsers.rst.directives.images import Image
    align = Image.align

options = {'alt': directives.unchanged,
           'height': directives.length_or_unitless,
           'width': directives.length_or_percentage_or_unitless,
           'scale': directives.nonnegative_int,
           'align': align,
           'class': directives.class_option,
           'include-source': directives.flag,
           'linenos': directives.flag}

template = """
.. htmlonly::
   .. image:: %(outdir)s/%(basename)s.png
%(options)s

.. latexonly::
   .. image:: %(outdir)s/%(basename)s.pdf
%(options)s

"""

def makefig(fullpath, outdir):
    """
    run a pyplot script<t and save the low and high res PNGs and a PDF in _static
    """

    fullpath = str(fullpath)  # todo, why is unicode breaking this
    formats = [('png', 100),
               ('pdf', 72),
               ]

    (basedir, fname) = os.path.split(fullpath)
    (basename, ext) = os.path.splitext(fname)
    all_exists = True

    if basedir != outdir:
        shutil.copyfile(fullpath, os.path.join(outdir, fname))

    for (format, dpi) in formats:
        outname = os.path.join(outdir, '%s.%s' % (basename, format))
        if not os.path.exists(outname):
            all_exists = False
            break

    if all_exists:
        print '    already have %s'%fullpath
        return

    print '    building %s'%fullpath
    plt.close('all')    # we need to clear between runs
    matplotlib.rcdefaults()

    run_path = os.path.join(outdir, fname)
    run_script = open(run_path, 'w')
    orig_script = open(fullpath, 'r')

    # remove plt.show() from scripts because we are going to save the figures
    # to a specified directory instead
    run_script.write('\n'.join([
        x for x in orig_script.read().split('\n') if x != 'plt.show()'
    ]))
    orig_script.close()
    run_script.close()

    # import module
    mdl = imp.load_source('plot', run_path)

    for format, dpi in formats:
        outname = os.path.join(outdir, '%s.%s' % (basename, format))
        if os.path.exists(outname): continue
        mdl.plt.savefig(outname, dpi=dpi)

def run(arguments, options, state_machine, lineno):
    reference = directives.uri(arguments[0])
    (basedir, fname) = os.path.split(reference)
    (basename, ext) = os.path.splitext(fname)

    path_parts = list(os.getcwd().split(os.path.sep))
    doc_idx = path_parts.index('doc')

    # change to doc directory if not already there
    for x in range(len(path_parts) - 1 - doc_idx): os.chdir('..')

    srcdir = 'source/lib'
    outdir = 'build/plots'

    outdir = os.path.abspath(outdir)
    srcdir = os.path.abspath(srcdir)

    # Make sure that outdir exists and is an actual directory
    if not os.path.isdir(outdir): os.mkdir(outdir)

    # Build the figure from the script
    makefig(os.path.join(srcdir, reference), outdir)

    # Process the options
    if 'include-source' in options:
        del options['include-source']
        lines = [".. literalinclude:: %(srcdir)s/%(reference)s" % locals()]
    else:
        lines = []

    options = ['      :%s: %s' % (k, v) for (k, v) in options.items()]
    options = "\n".join(options)

    lines.extend((template % locals()).split('\n'))

    state_machine.insert_input(lines, state_machine.input_lines.source(0))
    return []


try:
    from docutils.parsers.rst import Directive
except ImportError:
    from docutils.parsers.rst.directives import _directives

    def plot_directive(name, arguments, options, content, lineno,
                       content_offset, block_text, state, state_machine):
        return run(arguments, options, state_machine, lineno)
    plot_directive.__doc__ = __doc__
    plot_directive.arguments = (1, 0, 1)
    plot_directive.options = options

    _directives['plot'] = plot_directive
else:
    class plot_directive(Directive):
        required_arguments = 1
        optional_arguments = 0
        final_argument_whitespace = True
        option_spec = options
        def run(self):
            return run(self.arguments, self.options,
                       self.state_machine, self.lineno)
    plot_directive.__doc__ = __doc__

    directives.register_directive('plot', plot_directive)


def setup(app):
    #
    app.add_config_value('plotting_scripts_directory', None, True)