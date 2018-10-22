import numpy as np
from scipy.sparse import issparse


def show_proportions(adata):
    """Fraction of spliced/unspliced/ambiguous abundances

    Arguments
    ---------
    adata: :class:`~anndata.AnnData`
        Annotated data matrix.

    Returns
    -------
    Prints the fractions of abundances.
    """
    layers_keys = [key for key in ['spliced', 'unspliced', 'ambiguous'] if key in adata.layers.keys()]
    tot_mol_cell_layers = [adata.layers[key].sum(1) for key in layers_keys]

    mean_abundances = np.round(
        [np.mean(tot_mol_cell / np.sum(tot_mol_cell_layers, 0)) for tot_mol_cell in tot_mol_cell_layers], 2)

    print('Abundance of ' + str(layers_keys) + ': ' + str(mean_abundances))


def cleanup(data, clean='layers', keep={'spliced', 'unspliced'}, copy=False):
    """Deletes attributes not needed.

    Arguments
    ---------
    data: :class:`~anndata.AnnData`
        Annotated data matrix.
    cleanup: `str` or list of `str` (default: `layers`)
        Which attributes to consider for freeing memory.
    keep: `str` or list of `str` (default: `['spliced', unspliced']`)
        Which attributes to keep.
    copy: `bool` (default: `False`)
        Return a copy instead of writing to adata.

    Returns
    -------
    Returns or updates `adata` with selection of attributes kept.
    """
    adata = data.copy() if copy else data

    if any(['obs' in clean, 'all' in clean]):
        for key in list(adata.obs.keys()):
            if key not in keep: del adata.obs[key]

    if any(['var' in clean, 'all' in clean]):
        for key in list(adata.var.keys()):
            if key not in keep: del adata.var[key]

    if any(['uns' in clean, 'all' in clean]):
        for key in list(adata.uns.keys()):
            if key not in keep: del adata.uns[key]

    if any(['layers' in clean, 'all' in clean]):
        for key in list(adata.layers.keys()):  # remove layers that are not needed
            if key not in keep: del adata.layers[key]

    return adata if copy else None


def set_initial_size(adata, layers={'spliced', 'unspliced'}):
    if all([layer in adata.layers.keys() for layer in layers]):
        for layer in layers:
            X = adata.layers[layer]
            adata.obs['initial_size_' + layer] = X.sum(1).A1.copy() if issparse(X) else X.sum(1).copy()


def filter_genes(data, min_counts=3, min_cells=None, max_counts=None, max_cells=None,
                 min_counts_u=3,  min_cells_u=None, max_counts_u=None, max_cells_u=None, copy=False):
    """Filter genes based on number of cells or counts.
    Keep genes that have at least `min_counts` counts or are expressed in at
    least `min_cells` cells or have at most `max_counts` counts or are expressed
    in at most `max_cells` cells.
    Only provide one of the optional parameters `min_counts`, `min_cells`,
    `max_counts`, `max_cells` per call.
    Parameters
    ----------
    data : :class:`~anndata.AnnData`, `np.ndarray`, `sp.spmatrix`
        The (annotated) data matrix of shape `n_obs` × `n_vars`. Rows correspond
        to cells and columns to genes.
    min_counts : `int`, optional (default: `None`)
        Minimum number of counts required for a gene to pass filtering.
    min_cells : `int`, optional (default: `None`)
        Minimum number of cells expressed required for a gene to pass filtering.
    max_counts : `int`, optional (default: `None`)
        Maximum number of counts required for a gene to pass filtering.
    max_cells : `int`, optional (default: `None`)
        Maximum number of cells expressed required for a gene to pass filtering.
    min_counts_u : `int`, optional (default: `None`)
        Minimum number of unspliced counts required for a gene to pass filtering.
    min_cells_u : `int`, optional (default: `None`)
        Minimum number of unspliced cells expressed required for a gene to pass filtering.
    max_counts_u : `int`, optional (default: `None`)
        Maximum number of unspliced counts required for a gene to pass filtering.
    max_cells_u : `int`, optional (default: `None`)
        Maximum number of unspliced cells expressed required for a gene to pass filtering.
    copy : `bool`, optional (default: `False`)
        If an :class:`~anndata.AnnData` is passed, determines whether a copy
        is returned.
    Returns
    -------
    If `data` is an :class:`~anndata.AnnData`, filters the object and adds\
    either `n_cells` or `n_counts` to `adata.var`. Otherwise a tuple
    gene_subset : `np.ndarray`
        Boolean index mask that does filtering. `True` means that the gene is
        kept. `False` means the gene is removed.
    number_per_gene : `np.ndarray`
        Either `n_counts` or `n_cells` per gene.
    """
    adata = data.copy() if copy else data
    from scanpy.api.pp import filter_genes

    # set initial cell sizes before filtering
    if all([key in adata.layers.keys() for key in {'spliced', 'unspliced'}]): set_initial_size(adata)

    if min_counts is not None: filter_genes(adata, min_counts=min_counts)
    if max_counts is not None: filter_genes(adata, max_counts=max_counts)
    if min_cells is not None: filter_genes(adata, min_cells=min_cells)
    if max_cells is not None: filter_genes(adata, max_cells=max_cells)

    def filter_genes_u(adata, min_counts_u=None, min_cells_u=None, max_counts_u=None, max_cells_u=None, layer='unspliced'):
        counts = adata.layers[layer] if (min_counts_u is not None and max_counts_u is None) else adata.layers[layer] > 0
        counts = counts.sum(0).A1 if issparse(counts) else counts.sum(0)
        lb = min_counts_u if min_counts_u is not None else min_cells_u if min_cells_u is not None else -np.inf
        ub = max_counts_u if max_counts_u is not None else max_cells_u if max_cells_u is not None else np.inf
        adata._inplace_subset_var((lb <= counts) & (counts <= ub))

    if 'unspliced' in adata.layers.keys():
        if min_counts_u is not None or max_counts is not None:
            filter_genes_u(adata, min_counts_u=min_counts_u, max_counts_u=max_counts_u)
        if min_cells_u is not None or max_cells_u is not None:
            filter_genes_u(adata, min_cells_u=min_cells_u, max_cells_u=max_cells_u)

    return adata if copy else None


def filter_genes_dispersion(data, flavor='seurat', min_disp=None, max_disp=None, min_mean=None, max_mean=None,
                            n_bins=20, n_top_genes=None, copy=False):
    """Extract highly variable genes.
    The normalized dispersion is obtained by scaling with the mean and standard
    deviation of the dispersions for genes falling into a given bin for mean
    expression of genes. This means that for each bin of mean expression, highly
    variable genes are selected.
    Parameters
    ----------
    data : :class:`~anndata.AnnData`, `np.ndarray`, `sp.sparse`
        The (annotated) data matrix of shape `n_obs` × `n_vars`. Rows correspond
        to cells and columns to genes.
    flavor : {'seurat', 'cell_ranger', 'svr'}, optional (default: 'seurat')
        Choose the flavor for computing normalized dispersion. If choosing
        'seurat', this expects non-logarithmized data - the logarithm of mean
        and dispersion is taken internally when `log` is at its default value
        `True`. For 'cell_ranger', this is usually called for logarithmized data
        - in this case you should set `log` to `False`. In their default
        workflows, Seurat passes the cutoffs whereas Cell Ranger passes
        `n_top_genes`.
    min_mean=0.0125, max_mean=3, min_disp=0.5, max_disp=`None` : `float`, optional
        If `n_top_genes` unequals `None`, these cutoffs for the means and the
        normalized dispersions are ignored.
    n_bins : `int` (default: 20)
        Number of bins for binning the mean gene expression. Normalization is
        done with respect to each bin. If just a single gene falls into a bin,
        the normalized dispersion is artificially set to 1. You'll be informed
        about this if you set `settings.verbosity = 4`.
    n_top_genes : `int` or `None` (default: `None`)
        Number of highly-variable genes to keep.
    log : `bool`, optional (default: `True`)
        Use the logarithm of the mean to variance ratio.
    subset : `bool`, optional (default: `True`)
        Keep highly-variable genes only (if True) else write a bool array for h
        ighly-variable genes while keeping all genes
    copy : `bool`, optional (default: `False`)
        If an :class:`~anndata.AnnData` is passed, determines whether a copy
        is returned.
    Returns
    -------
    If an AnnData `adata` is passed, returns or updates `adata` depending on \
    `copy`. It filters the `adata` and adds the annotations
    """
    adata = data.copy() if copy else data
    if all([key in adata.layers.keys() for key in {'spliced', 'unspliced'}]): set_initial_size(adata)

    if n_top_genes is not None and n_top_genes < adata.shape[1]:
        #normalize_per_cell(adata)
        if flavor == 'svr':
            mu = adata.X.mean(0).A1 if issparse(adata.X) else adata.X.mean(0)
            sigma = np.sqrt(adata.X.multiply(adata.X).mean(0).A1 - mu**2) if issparse(adata.X) else adata.X.std(0)
            log_mu = np.log2(mu)
            log_cv = np.log2(sigma / mu)

            from sklearn.svm import SVR
            clf = SVR(gamma=150. / len(mu))
            clf.fit(log_mu[:, None], log_cv)
            score = log_cv - clf.predict(log_mu[:, None])
            nth_score = np.sort(score)[::-1][n_top_genes]
            adata._inplace_subset_var(score >= nth_score)
        else:
            from scanpy.api.pp import filter_genes_dispersion
            filter_genes_dispersion(adata, flavor=flavor, min_disp=min_disp, max_disp=max_disp, min_mean=min_mean,
                                    max_mean=max_mean, n_bins=n_bins, n_top_genes=n_top_genes)
    return adata if copy else None


def normalize_layers(data, layers={'spliced', 'unspliced'}, copy=False):
    """Filtering, normalization and log transform

    Expects non-logarithmized data. If using logarithmized data, pass `log=False`.

    Runs the following steps

    .. code:: python

        sc.pp.filter_genes(adata, min_counts=10)
        sc.pp.normalize_per_cell(adata)
        sc.pp.filter_genes_dispersion(adata, n_top_genes=10000)
        sc.pp.normalize_per_cell(adata)
        if log: sc.pp.log1p(adata)


    Arguments
    ---------
    data: :class:`~anndata.AnnData`
        Annotated data matrix.
    min_counts: `int` (default: 10)
        Minimum number of gene counts per cell.
    n_top_genes: `int` (default: 10000)
        Number of genes to keep.
    log: `bool` (default: `True`)
        Take logarithm.
    copy: `bool` (default: `False`)
        Return a copy of `adata` instead of updating it.

    Returns
    -------
    Returns or updates `adata` depending on `copy`.
    """

    """Normalize by total counts to median
    """
    adata = data.copy() if copy else data
    from scanpy.api.pp import normalize_per_cell

    def get_size_and_bool(adata, layer):
        if layer not in {'spliced', 'unspliced'}:
            return None, True
        else:
            size = adata.obs['initial_size_' + layer].copy() if 'initial_size_' + layer in adata.obs.keys() else None
            X = adata.layers[layer]
        return size, np.allclose((X.data[:10] if issparse(X) else X[0]) % 1, 0, atol=1e-3)

    for layer in layers:
        size, not_yet_normalized = get_size_and_bool(adata, layer)
        if not_yet_normalized:
            adata.layers[layer] = normalize_per_cell(adata.layers[layer], None, size, copy=True)
    return adata if copy else None


def normalize_per_cell(data, counts_per_cell_after=None, counts_per_cell=None,
                       key_n_counts=None, log=True, copy=False):
    """Normalize total counts per cell.
    Normalize each cell by total counts over all genes, so that every cell has
    the same total count after normalization.
    Parameters
    ----------
    data : :class:`~anndata.AnnData`, `np.ndarray`, `sp.sparse`
        The (annotated) data matrix of shape `n_obs` × `n_vars`. Rows correspond
        to cells and columns to genes.
    counts_per_cell_after : `float` or `None`, optional (default: `None`)
        If `None`, after normalization, each cell has a total count equal
        to the median of the *counts_per_cell* before normalization.
    counts_per_cell : `np.array`, optional (default: `None`)
        Precomputed counts per cell.
    key_n_counts : `str`, optional (default: `'n_counts'`)
        Name of the field in `adata.obs` where the total counts per cell are
        stored.
    copy : `bool`, optional (default: `False`)
        If an :class:`~anndata.AnnData` is passed, determines whether a copy
        is returned.
    Returns
    -------
    Returns or updates `adata` with normalized version of the original
    `adata.X`, depending on `copy`.
    """
    adata = data.copy() if copy else data
    from scanpy.api.pp import normalize_per_cell, log1p
    if counts_per_cell is None and 'initial_size_spliced' in adata.obs.keys():
        counts_per_cell = adata.obs['initial_size_spliced'].copy()
    normalize_per_cell(adata, counts_per_cell_after, counts_per_cell, key_n_counts)
    normalize_layers(adata)
    if log: log1p(adata)
    return adata if copy else None


def filter_and_normalize(data, min_counts=3, min_counts_u=3, min_cells=None, min_cells_u=None, n_top_genes=None,
                         log=True, flavor='seurat', copy=False):
    """Runs pp.filter_genes(), pp.filter_genes_dispersion() and pp.normalize_per_cell()
    """
    adata = data.copy() if copy else data
    filter_genes(adata, min_counts=min_counts, min_counts_u=min_counts_u, min_cells=min_cells, min_cells_u=min_cells_u)
    filter_genes_dispersion(adata, n_top_genes=n_top_genes, flavor=flavor)
    normalize_per_cell(adata, log=log)
    return adata if copy else None


def recipe_velocity(adata, min_counts=3, min_counts_u=3, n_top_genes=None, n_pcs=30, n_neighbors=30, log=True, copy=False):
    """Runs pp.filter_and_normalize() and pp.moments()
    """
    from .moments import moments
    filter_and_normalize(adata, min_counts=min_counts, min_counts_u=min_counts_u, n_top_genes=n_top_genes, log=log)
    moments(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)
    return adata if copy else None
