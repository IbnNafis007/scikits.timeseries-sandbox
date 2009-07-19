"""
Extras functions for time series.

:author: Pierre GF Gerard-Marchant & Matt Knox
:contact: pierregm_at_uga_dot_edu - mattknox_ca_at_hotmail_dot_com
:version: $Id$
"""
__author__ = "Pierre GF Gerard-Marchant & Matt Knox ($Author$)"
__revision__ = "$Revision$"
__date__     = '$Date$'


import numpy as np
import numpy.ma as ma

from numpy import genfromtxt
from numpy.ma import masked

import const as _c
from tdates import Date, date_array
from tseries import TimeSeries, time_series

#from _preview import genfromtxt

__all__ = ['accept_atmost_missing',
           'convert_to_annual', 'count_missing',
           'guess_freq',
           'isleapyear',
           'tsfromtxt']

#..............................................................................
def isleapyear(year):
    """
    Returns true if year is a leap year.

    Parameters
    ----------
    year : integer / sequence
        A given (list of) year(s).
    """
    year = np.asarray(year)
    return np.logical_or(year % 400 == 0,
                         np.logical_and(year % 4 == 0, year % 100 > 0))

#..............................................................................
def count_missing(series):
    """
    Returns the number of missing data per period.

    Notes
    -----
    This function is designed to return the actual number of missing values when
    a series has been converted from one frequency to a smaller frequency.

    For example, converting a 12-month-long daily series to months will yield
    a (12x31) array, with missing values in February, April, June...
    count_missing will discard these extra missing values.
    """
    if not isinstance(series, TimeSeries):
        raise TypeError, "The input data should be a valid TimeSeries object! "\
                         "(got %s instead)" % type(series)
    if series.ndim == 1:
        return len(series) - series.count()
    elif series.ndim != 2:
        raise NotImplementedError
    #
    missing =  series.shape[-1] - series.count(axis=-1)
    period = series.shape[-1]
    freq = series.freq
    if (period == 366) and (freq//_c.FR_ANN == 1):
        # row: years, cols: days
        missing -= ~isleapyear(series.year)
    elif period == 31 and (freq//_c.FR_MTH == 1):
        months = series.months
        # row: months, cols: days
        missing[np.array([m in [4,6,9,11] for m in months])] -= 1
        isfeb = (months == 2)
        missing[isfeb] -= 2
        missing[isfeb & ~isleapyear(series.year)] -= 1
    elif period == 92 and (freq//_c.FR_QTR == 1):
        # row: quarters, cold:days
        months = series.months
        if freq in (_c.FR_QTREJAN, _c.FR_QTRSJAN, _c.FR_QTREAPR, _c.FR_QTRSAPR,
                    _c.FR_QTREOCT, _c.FR_QTRSOCT, _c.FR_QTREOCT, _c.FR_QTRSOCT):
            isfeb = (months == 4)
            missing[isfeb] -= 2
        elif freq in (_c.FR_QTREFEB, _c.FR_QTRSFEB, _c.FR_QTREMAY, _c.FR_QTRSMAY,
                      _c.FR_QTREAUG, _c.FR_QTRSAUG, _c.FR_QTRENOV, _c.FR_QTRSNOV):
            missing[np.array([m in [2,11] for m in months])] -= 1
            isfeb = (months == 2)
        elif freq in (_c.FR_QTREMAR, _c.FR_QTRSMAR, _c.FR_QTREJUN, _c.FR_QTRSJUN,
                      _c.FR_QTRESEP, _c.FR_QTRSSEP, _c.FR_QTREDEC, _c.FR_QTRSDEC):
            missing[np.array([m in [3,6] for m in months])] -= 1
            isfeb = (months == 3)
        missing[isfeb & ~isleapyear(series.year)] -= 1
    elif period not in (12,7):
        raise NotImplementedError, "Not yet implemented for that frequency..."
    return missing



def convert_to_annual(series):
    """
    Group a series by years, taking leap years into account.
    
    The output has as many rows as distinct years in the original series,
    and as many columns as the length of a leap year in the units corresponding
    to the original frequency (366 for daily frequency, 366*24 for hourly...).
    The fist column of the output corresponds to Jan. 1st, 00:00:00,
    while the last column corresponds to Dec, 31st, 23:59:59.
    Entries corresponding to Feb. 29th are masked for non-leap years.

    For example, if the initial series has a daily frequency, the 59th column
    of the output always corresponds to Feb. 28th, the 61st column to Mar. 1st,
    and the 60th column is masked for non-leap years.
    With a hourly initial frequency, the (59*24)th column of the output always
    correspond to Feb. 28th 23:00, the (61*24)th column to Mar. 1st, 00:00, and
    the 24 columns between (59*24) and (61*24) are masked.

    If the original frequency is less than daily, the output is equivalent to
    ``series.convert('A', func=None)``.


    Parameters
    ----------
    series : TimeSeries
        A valid :class:`~scikits.timeseries.TimeSeries` object.

    Returns
    -------
    aseries : TimeSeries
        A 2D  :class:`~scikits.timeseries.TimeSeries` object with annual ('A')
        frequency.
    
    """
    freq = series._dates.freq
    if freq < _c.FR_DAY:
        return series.convert('A')
    baseidx = np.array((59, 60), dtype=int)
    if (freq == _c.FR_DAY):
        (idx0228, idx0301) = baseidx
    elif (freq == _c.FR_HR):
        (idx0228, idx0301) = baseidx*24
    elif (freq == _c.FR_MIN):
        (idx0228, idx0301) = baseidx*24*60
    elif (freq == _c.FR_SEC):
        (idx0228, idx0301) = baseidx*24*3600
    aseries = series.convert('A')
    leapcondition = isleapyear(aseries.dates.years)
    leapidx = np.arange(len(aseries), dtype=int)[~leapcondition]
    aseries[leapidx, idx0301:] = aseries[leapidx, idx0228:idx0228-idx0301]
    aseries[leapidx, idx0228:idx0301] = ma.masked
    return aseries



#.............................................................................
def accept_atmost_missing(series, max_missing, strict=False):
    """
    Masks the rows of `series` that contain more than `max_missing` missing data.
    Returns a new masked series.

    Parameters
    ----------
    series : TimeSeries
        Input time series.
    max_missing : float
        Number of maximum acceptable missing values per row (if larger than 1),
        or maximum acceptable percentage of missing values (if lower than 1).
    strict : boolean *[False]*
        Whether the number of missing values should be strictly greater than
        `max_missing` or not.

    Returns
    -------
    output : TimeSeries
        A new TimeSeries object
    """
    series = np.array(series, copy=True, subok=True)
    if not isinstance(series, TimeSeries):
        raise TypeError, "The input data should be a valid TimeSeries object! "\
                         "(got %s instead)" % type(series)
    # Find the number of missing values ....
    missing = count_missing(series)
    # Transform an acceptable percentage in a number
    if max_missing < 1:
        max_missing = np.round(max_missing * series.shape[-1],0)
    #
    series.unshare_mask()
    if strict:
        series[missing > max_missing] = masked
    else:
        series[missing >= max_missing] = masked
    return series

def guess_freq(dates):
    """
    Return an estimate of the frequency from a list of dates.

    The frequency is estimated from the difference of dates (in days or seconds)
    after chronological sorting.


    Parameters
    ----------
    dates : var
        Sequence of dates

    Notes
    -----
    * In practice, the list of dates is first transformed into a list of
      :class:`datetime.datetime` objects.
    * The estimated frequency can *never* be ``_c.FR_BUS`` (weekdays).
    """
    # Set to an array of datetimes
    dates = np.array(date_array(dates, freq='S').tolist())
    # Sort and take the differences
    ddif = np.diff(np.sort(dates))
    incs = np.fromiter((d.seconds for d in ddif), dtype=int)
    if incs.any():
        minincs = min(incs)
        if (minincs > 3599) and not np.all(incs % 3600 > 0):
            freq = _c.FR_HR
        elif minincs < 59:
            freq = _c.FR_SEC
        else:
            freq = _c.FR_MIN
        return freq
    incs = np.fromiter(((d.days % 365) for d in ddif), dtype=int)
    (mindays, maxdays) = (min(incs), max(incs))
    if mindays > 360:
        freq = _c.FR_ANN
    elif (mindays > 88):
        qincs = [89, 90, 91, 92, 273, 274, 275, 276, 277]
        if np.all([i in qincs for i in (incs % 365)]):
            freq = _c.FR_QTR
        else:
            freq = _c.FR_MTH
    elif (mindays > 27):
        freq = _c.FR_MTH
    elif (mindays % 7 == 0) and np.all((incs % 7) == 0):
        freq = _c.FR_WK
    else:
        freq = _c.FR_DAY
    return freq


def tsfromtxt(fname, dtype=None, freq='U', comments='#', delimiter=None,
              skiprows=0, converters=None, dateconverter=None,
              missing='', missing_values=None,
              usecols=None, datecols=None,
              names=None, excludelist=None, deletechars=None,
              case_sensitive=True, unpack=None, loose=True,
              asrecarray=False):
    """
    Load a TimeSeries from a text file.

    Each line of the input after the first `skiprows` ones is split at
    `delimiter`. Characters occuring after `comments` are discarded.

    If a column is named ``'dates'`` (case insensitive), it is used to define
    the dates. The ``freq`` parameter should be set to the expected frequency of
    the output series.
    If the date information spans several columns (for example, year in col #1,
    month in col #2...), a specific conversion function must be defined with
    the ``dateconverter`` parameter. This function should accept as many inputs
    as date columns, and return a valid :class:`Date` object.

    Parameters
    ----------
    fname : file or string
        File or filename to read.
        If the file extension is ``.gz`` or ``.bz2``, the file is first
        decompressed.
    dtype : data-type, optional
        Data type of the resulting array.
        If it is a structured data-type, the resulting array is 1-dimensional,
        and each row is interpreted as an element of the array. In this case, 
        the number of columns used must match the number of fields in the dtype
        and the names of each field are set by the corresponding name of the dtype.
        If None, the dtypes will be determined by the contents of each
        column, individually.
    comments : {string}, optional
        The character used to indicate the start of a comment.
        All the characters occurring on a line after a comment are discarded.
    delimiter : {string}, optional
        The string used to separate values.  By default, any consecutive
        whitespace act as delimiter.
    skiprows : {int}, optional
        Numbers of lines to skip at the beginning of the file.
    converters : {None, dictionary}, optional
        A dictionary mapping column number to a function that will convert
        values in the column to a number. Converters can also be used to
        provide a default value for missing data:
        ``converters = {3: lambda s: float(s or 0)}``.
    dateconverter : {function}, optional
        Function to convert the date information to a :class:`Date` object. 
        This function requires as many parameters as number of ``datecols``.
        This parameter is mandatory if ``dtype=None``.
    missing : {string}, optional
        A string representing a missing value, irrespective of the column where
        it appears (e.g., `'missing'` or `'unused'`).
    missing_values : {None, dictionary}, optional
        A dictionary mapping a column number to a string indicating whether the
        corresponding field should be masked.
    usecols : {None, sequence}, optional
        Which columns to read, with 0 the first column.  For example,
        ``usecols = (1,4,5)`` extracts the 2nd, 5th and 6th columns only.
    datecols : {None, int, sequence}, optional
        Which columns store the date information.
    names : {True, string, sequence}, optional
        If ``names`` is ``True``, the field names are read from the first
        valid line after the first ``skiprows`` lines.
        If it is a sequence or a single-string of comma-separated names,
        the names are used to define the field names in a structured dtype.
        If ``None``, the names of the ``dtype`` fields will be used, if any.
    excludelist : {sequence}, optional
        A list of names to exclude. This list is appended to the default list
        ``['return','file','print']``. 
        Excluded names are appended an underscore: for example, ``file`` would
        become ``file_``.
    deletechars : {string}, optional
        A string combining invalid characters that must be deleted from the names.
    case_sensitive : {True, False], optional
        Whether names are case sensitive. If not, names are transformed to 
        upper case.
    unpack : {bool}, optional
        If True, the returned array is transposed, so that arguments may be
        unpacked using ``x, y, z = loadtxt(...)``
    asrecarray : {False, True}, optional
        Whether to return a TimeSeriesRecords or a series with a structured 
        dtype.

    Returns
    -------
    out : MaskedArray
        Data read from the text file.

    Notes
    -----
    * When spaces are used as delimiters, or when no delimiter has been given
      as input, there should not be any missing data between two fields.
    * When the variable are named (either by a flexible dtype or with `names`,
      there must not be any header in the file (else a :exc:`ValueError`
      exception is raised).
    * If the datatype is not given explicitly (``dtype=None``),
      a :keyword:`dateconverter` must be given explicitly.

    Examples
    --------
    >>> data = "year, month, a, b\\n 2001, 01, 0.0, 10.\\n 2001, 02, 1.1, 11."
    >>> dateconverter = lambda y, m: Date('M', year=int(y), month=int(m))
    >>> series = tsfromtxt(StringIO.StringIO(data), delimiter=',', names=true,
    ...                    datecols=(0,1), dateconverter=dateconverter,)
    >>> series
    timeseries([(0.0, 10.0) (1.1, 11.0)],
       dtype = [('a', '<f8'), ('b', '<f8')],
       dates = [Jan-2001 Feb-2001],
       freq  = M)

    """
    # Update the date converter .......
    converters = converters or {}
    dateconv = dateconverter or None
    if dateconv is None:
        dateconv = lambda s: Date(freq, string=s)
    if 'dates' in converters:
        dateconv = converters['dates']
        del(converters['dates'])
    # Update the dtype (if needed) ....
    idtype = None
    if (dtype is not None):
        dtype = np.dtype(dtype)
        idtype = dtype
        # Crash if we can't find the datecols
        if datecols is None:
            raise TypeError("No column selected for the dates!")
        # Make sure we can iterate on the datecols
        if isinstance(datecols, (np.int, np.float)):
            datecols = (datecols,)
        # Update the converter
        update = [(_, str) for _ in datecols]
        # Don't use the ew structure just yet
        if dtype.names:
            convdict = {'b': bool, 'i': int, 'l':int, 'u': int,
                        'f': float, 'd': float, 'g': float,
                        'c': complex, 'D': complex, 
                        'S': str, 'U': str, 'a': str}
            dnames = dtype.names
            idx = range(len(datecols)+len(dnames))
            for i in datecols:
                del idx[idx.index(i)]
            update.extend([(i, convdict[dtype[name].char])
                           for (i, name) in zip(idx, dnames)])
            dtype = None
        converters.update(update)
        #
    # Update the optional arguments ...
    kwargs = dict(dtype=dtype, comments=comments, delimiter=delimiter, 
                  skiprows=skiprows, converters=converters,
                  missing=missing, missing_values=missing_values,
                  usecols=usecols, unpack=unpack, names=names, 
                  excludelist=excludelist, deletechars=deletechars,
                  case_sensitive=case_sensitive,
                  usemask=True)
    # Get the raw data ................
    mrec = genfromtxt(fname, **kwargs)
    if not mrec.shape:
        mrec.shape = -1
    names = mrec.dtype.names
    # Revert to the original dtype.....
    dtype = idtype
    # Get the date columns ............
    if datecols is None:
        import re
        datespattern = re.compile("'?_?dates?'?", re.IGNORECASE)
        datecols = [i for (i, name) in enumerate(names or ())
                     if datespattern.search(name)]
        if not datecols:
            raise TypeError("No column selected for the dates!")
    elif isinstance(datecols, (np.int, np.float)):
        datecols = (datecols,)
    # Fix the date columns if usecols was given
    if usecols is not None:
        datecols = tuple([list(usecols).index(d) for d in datecols])
    # Get the date info ...............
    if names:
        dateinfo = [mrec[names[i]] for i in datecols]
    else:
        dateinfo = [mrec[:,i] for i in datecols]
    if len(dateinfo) == 1:
        dateinfo = np.array(dateinfo[0], copy=False, ndmin=1)
        dates = date_array([dateconv(args) for args in dateinfo],
                           freq=freq, autosort=False)
    else:
        dates = date_array([dateconv(*args) for args in zip(*dateinfo)],
                           freq=freq, autosort=False)
    # Resort the array according to the dates
    sortidx = dates.argsort()
    dates = dates[sortidx]
    mrec = mrec[sortidx]
    # Get the dtype from the named columns (if any), or just use the initial one
    mdtype = mrec.dtype
    if mdtype.names:
        newdescr = [descr for (i, descr) in enumerate(mdtype.descr)
                    if i not in datecols]
        output = time_series(ma.empty((len(mrec),), dtype=newdescr),
                             dates=dates)
        for name in output.dtype.names:
            output[name] = mrec[name]
        if (idtype is not None):
            if (idtype.names is None):
                dtype = (idtype, len(output.dtype.names))
            else:
                dtype = idtype
            output = output.view(dtype)
    else:
        dataidx = [i for i in range(mrec.shape[-1]) if i not in datecols]
        if len(dataidx) == 1:
            dataidx = dataidx[0]
        output = time_series(mrec[:,dataidx], dates=dates)
    #
    if asrecarray:
        from trecords import TimeSeriesRecords
        return output.view(TimeSeriesRecords)
    return output
