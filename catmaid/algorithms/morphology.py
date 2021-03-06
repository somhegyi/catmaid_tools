#!/usr/bin/env python

import copy

import networkx

try:
    import numpy
    has_numpy = True
except ImportError:
    has_numpy = False


try:
    xrange
except NameError as E:
    xrange = range


def node_array(neuron, node_list=None, include_nid=False):
    '''
    node_array(neuron, node_list=None)
    Creates an array of cartesian coordinates (x, y and z) from an input Neuron

    Input:
     - Neuron    (from Neuron class)
     - node_list (list of nodes with xyz coordinates)

    Output:
     - Array of all nodes (with xyz coordinates) that are associated
       with the input Neuron
    '''
    if node_list is None:
        node_list = neuron.nodes.keys()
    nodes = []
    if include_nid:
        uf = lambda nid, n: (nid, n['x'], n['y'], n['z'])
    else:
        uf = lambda nid, n: (n['x'], n['y'], n['z'])
    nodes = [uf(nid, neuron.nodes[nid]) for nid in node_list]
    if has_numpy:
        return numpy.array(nodes)
    return nodes


def node_position(node):
    '''returns position of node or connector'''
    position = (node['x'], node['y'], node['z'])
    if has_numpy:
        return numpy.array(position)
    return position


def node_edge_array(neuron):
    n2a = {}
    nodes = []
    edges = []

    def to_xyz(nid):
        n = neuron.nodes[nid]
        return (n['x'], n['y'], n['z'])

    for c in neuron.edges:
        p = neuron.edges[c]
        if c not in n2a:
            nodes.append(to_xyz(c))
            caid = len(nodes) - 1
            n2a[c] = caid
        else:
            caid = n2a[c]
        for sp in p:
            if sp not in n2a:
                nodes.append(to_xyz(sp))
                paid = len(nodes) - 1
                n2a[sp] = paid
            else:
                paid = n2a[sp]
            edges.append((caid, paid))
    if has_numpy:
        return numpy.array(nodes), numpy.array(edges)
    return nodes, edges


def resampled_edge_array(neuron, graph=None, distance=40):
    """Returns an array of [sx sy sz ex ey ez], where s=start/e=end of edge"""
    edge_array = []
    if graph is None:
        graph = neuron.dgraph
    for u, v in graph.edges_iter():
        un = neuron.nodes[u]
        vn = neuron.nodes[v]
        up = numpy.array([un['x'], un['y'], un['z']], dtype='f8')
        vp = numpy.array([vn['x'], vn['y'], vn['z']], dtype='f8')
        d = numpy.linalg.norm(vp - up)
        if d > distance:
            # resample this
            s = up
            delta = distance
            n = (vp - up) / d
            # print d, up, vp
            while delta < d:
                # compute new point that is delta away from p
                e = n * delta + up
                # print numpy.linalg.norm(e - s), s, e
                edge_array.append(numpy.hstack((s, e)))
                s = e
                delta += distance
            # print numpy.linalg.norm(vp - s), s, vp
            edge_array.append(numpy.hstack((s, vp)))
        else:
            edge_array.append(numpy.hstack((up, vp)))
    return numpy.array(edge_array)


def resampled_node_array(
        neuron, graph=None, distance=40, start=None, end=None, nodes=None,
        edges=None):
    '''
    resampled_node_array(neuron, graph=None, distance=40, start=None, end=None,
                         nodes=None, edges=None)

    Creates an array of cartesian coordinates that includes nodes of an input
       Neuron, as well as coordinates interpolated between neighboring nodes.
       This triples the length of the node array for added precision.

    Input:
     - Neuron   (from Neuron class)
     - graph    (directed graph of Neuron generated by networkx)
     - distance (thickness of EM slices, 40nm in our case)
     - start    (Node ID where the algorithm begins (default is the root node))
     - nodes    (Array of nodes on which to run the algoritm
                (default is all nodes of input neuron))
     - edges    (TODO?)

    Output:
     - array of cartesian coordinates containing the nodes of the input Neuron,
       as well as coordinates interpolated between neighboring nodes

    '''
    if graph is None:
        graph = neuron.dgraph
    if start is None:
        pred = graph.pred
        start = [i for i in pred if len(pred[i]) == 0][0]
    if nodes is None:
        nodes = []
    if edges is None:
        edges = []
    while start is not None:
        if end is None:
            succ = graph.succ
            if len(succ[start]) == 0:
                return nodes
            elif len(succ[start]) > 1:
                vs = succ[start].keys()
                end = vs[0]
                for other in vs[1:]:
                    nodes = resampled_node_array(
                        neuron, graph, distance, start, other, nodes, edges)
            else:
                end = succ[start].keys()[0]
        sn = neuron.nodes[start]
        en = neuron.nodes[end]
        l = sum([(sn[k] - en[k]) ** 2. for k in ('x', 'y', 'z')]) ** 0.5
        if l < distance:
            nodes.append((sn['x'], sn['y'], sn['z']))
            # TODO edges?
            # new_graph.add_edge(start, end)
        else:
            # origin is sn
            origin = (sn['x'], sn['y'], sn['z'])
            # slope is en - sn
            slope = (en['x'] - sn['x'], en['y'] - sn['y'], en['z'] - sn['z'])
            scale = distance / float(l)
            breaks = int(l / distance)
            # print("Resampling %s into %s" % (l, breaks))
            origin_id = start
            for i in xrange(breaks):
                # compute position of new point
                new_point = (
                    origin[0] + slope[0] * scale,
                    origin[1] + slope[1] * scale,
                    origin[2] + slope[2] * scale)

                # add edge to graph
                nodes.append(origin)
                # TODO edges?

                # reset for next loop
                origin = new_point
            # add edge to graph
            nodes.append(origin)
            # TODO edges?
        start = end
        end = None
    return nodes


def midpoint(neuron, v0, v1):
    """
    midpoint(neuron, v0, v1)

    Returns euclidian midpoint between v0 and v1

    Input:
     - Neuron (from Neuron class)
     - v0 (string representing node ID from Neuron)
     - v1 (string representing node ID from Neuron)

    Output:
     - Midpoint between v0 and v1 in xyz
    """
    return dict([
        (d, (neuron.skeleton['vertices'][v0][d] +
             neuron.skeleton['vertices'][v1][d]) / 2.)
        for d in ('x', 'y', 'z')])


def distance(neuron, v0, v1):
    """
    distance(neuron, v0, v1)

    Returns the distance between v0 and v1

    Input:
     - Neuron (from Neuron class)
     - v0 (string representing node ID from Neuron)
     - v1 (string representing node ID from Neuron)

    Output:
     - distance between v0 and v1 in 3D space
    """
    return sum([
        (neuron.skeleton['vertices'][v0][k] -
         neuron.skeleton['vertices'][v1][k]) ** 2.
        for k in ('x', 'y', 'z')]) ** 0.5


def find_path(neuron, v0, v1):
    """
    find_path(neuron, v0, v1)

    Finds the shortest path between v0 and v1 using networkx functions

    Input:
     - Neuron (from Neuron class)
     - v0 (string representing node ID from Neuron)
     - v1 (string representing node ID from Neuron)

    Output:
     - An array of node IDs, or a Non-directed networkx graph representing the
       shortest path between v0 and v1
    """
    return networkx.shortest_path(neuron.graph, v0, v1)


def path_length(neuron, v0, v1):
    """
    path_length(neuron, v0, v1)

    Finds the length of the shortest path between v0 and v1 using
    distance function

    Input:
     - Neuron (from Neuron class)
     - v0 (string representing node ID from Neuron)
     - v1 (string representing node ID from Neuron)

    Output:
     - sum of distances between each node in the shortest path between v0 and
       v1 in 3D space
    """
    path = find_path(neuron, v0, v1)
    return sum([
        distance(neuron, path[i], path[i+1]) for i in xrange(len(path) - 1)])


def branch_order(neuron, v, base=None):
    """if base is None, default to soma"""
    if base is None:
        base = neuron.soma
        if neuron.soma is None:
            return None
    path = networkx.shortest_path(neuron.graph, base, v)
    order = 0
    for v in path:
        if len(neuron.edges[v]) > 2:
            order += 1
    return order


def center_of_mass(neuron):
    """
    center_of_mass(neuron)

    Finds the center of mass of the neuron

    Input:
     - Neuron (from Neuron class)

    Output:
     - xyz coordinates representing the physical center of mass of the Neuron
    """
    # it's a series of tubes!
    com = {'x': 0., 'y': 0., 'z': 0.}
    mass = 0.
    edges = neuron.edges
    for e0 in edges:
        for e1 in edges[e0]:
            # distance between nodes
            m = midpoint(neuron, e0, e1)
            d = distance(neuron, e0, e1)
            com['x'] += m['x'] * d
            com['y'] += m['y'] * d
            com['z'] += m['z'] * d
            mass += d
    # avoid dividing by 0
    if mass == 0.:
        return {'x': float('nan'), 'y': float('nan'), 'z': float('nan')}
    com['x'] /= mass
    com['y'] /= mass
    com['z'] /= mass
    return com


def unique_neurites(neu, base=None):
    '''
    This function generates lists of unique neurites based off branching
        structure of neuron object
    '''
    if base is None:
        base = neu.root
    neurites = []
    for bifurcation in neu.bifurcations:
        if bifurcation == base:
            continue
        # Loop through bifurcations
        path = networkx.shortest_path(neu.graph, base, bifurcation)
        # Pull out any additional bifurcations found in path
        bifurcations = [b for b in neu.bifurcations if
                        (b in path and b != bifurcation)]
        if len(bifurcations) > 0:
            for b in bifurcations:
                # Find path between bifurcation1 and bifurcation2
                b_to_b = networkx.shortest_path(neu.graph, b, bifurcation)
                # Check for any additional bifurcaions between new path
                bfcs = [bi for bi in neu.bifurcations if
                        (bi in b_to_b and bi != bifurcation and bi != b)]
                if len(bfcs) > 0:
                    # This path is not vaild
                    continue
                else:
                    # This is a valid path
                    neurites.append(b_to_b)
        else:
            # This is a valid path
            neurites.append(path)
    for leaf in neu.leaves:
        # Calculate shortest path
        path = networkx.shortest_path(neu.graph, base, leaf)
        # Find any bifurcations in path
        bifurcations = [bs for bs in neu.bifurcations if bs in path]
        if len(bifurcations) > 0:
            for b in bifurcations:
                # Calculate path from bifurcation to leaf
                b_to_l = networkx.shortest_path(neu.graph, b, leaf)
                # Find any additional bifurcations within new path
                bfcs = [bi for bi in neu.bifurcations if
                        (bi in b_to_l and bi != b)]
                if len(bfcs) > 0:
                    # This path is not valid
                    continue
                else:
                    # This path is valid
                    neurites.append(b_to_l)
        else:
            # This path is valid
            neurites.append(path)
    return list(set([tuple(neurite) for neurite in neurites]))


def total_pathlength(neuron):
    return sum([sum([distance(neuron, path[i], path[i+1])
                     for i in xrange(len(path) - 1)])
                for path in unique_neurites(neuron)])


def root_to_leaf_pathlengths(neuron):
    if len(neuron.leaves) > 0:
        return [path_length(
            neuron, neuron.root, leaf) for leaf in neuron.leaves]
    else:
        return None


def longest_pathlength(neuron):
    """ This function will return the length of the longest pathlength
    for a given neuron"""
    if len(neuron.nodes) == 1:
        return 0.
    if len(neuron.bifurcations) == 0:
        paths = root_to_leaf_pathlengths(neuron)
        if paths:
            return max(paths)
        else:
            return 0.
    else:
        return max([sum([distance(neuron, path[i], path[i+1])
                         for i in xrange(len(path) - 1)])
                    for path in unique_neurites(neuron)])


def longest_node_pathlength(neuron):
    """ This function will return an array containing the nodes of the
    longest pathlength for a given neuron"""
    if len(neuron.nodes) == 1:
        print "{} has length of 0 (only 1 node)".format(neuron.skeleton_id)
        return 0.
    if len(neuron.leaves) == 1:
        return find_path(neuron, neuron.root, neuron.leaves[0])
    else:
        longest = []
        for leaf1 in neuron.leaves:
            for leaf2 in neuron.leaves:
                pathlength = find_path(neuron, leaf1, leaf2)
                if len(pathlength) > len(longest):
                    longest = pathlength
    return longest


def soma_through_projection_to_leaf(source, skeleton_id=None, neuron=None):
    """IMPORTANT! This function requires networkx version 1.10 or greater!
       This function will find the path from a neurons soma to leaf by
       passing through an axon or projection tag"""
    if not skeleton_id and not neuron:
        raise Exception("Must provide skeleton_id or neuron")
    if skeleton_id and not neuron:
        neuron = source.get_neuron(skeleton_id)
    try:
        soma = neuron.tags['soma']
    except KeyError:
        print ("CONTOUR ERROR: Skipping skeleton %s. "
               "No soma found" % neuron.skeleton_id)
        return None
    if any([('axon' in tag) for tag in neuron.tags]):
        projection = neuron.tags['axon']
        projection_graph = neuron.axons[projection[0]]['tree']
        print "AXON FOUND: Skelton %s." % neuron.skeleton_id
    else:
        try:
            projection = neuron.tags['projection']
            if len(projection) > 1:
                print ("CONTOUR ERROR: Skel {} has more than one "
                       "projection tag".format(neuron.skeleton_id))
            projection_graph = neuron.projection[projection[0]]['tree']
            print "PROJECTION FOUND: skeleton %s." % neuron.skeleton_id
        except:
            print ("CONTOUR ERROR: Skipping skeleton %s. No Axon or Projection"
                   " tag found!" % neuron.skeleton_id)
            return None
    longest_path = networkx.dag_longest_path(projection_graph)
    soma_to_projection = networkx.shortest_path(neuron.graph, soma[0],
                                                projection[0])
    soma_to_projection.remove(projection[0])
    projection_path = soma_to_projection + longest_path
    return projection_path


def backbone_to_backbone(source, skeleton_id=None, neuron=None):
    """IMPORTANT! This function requires networkx version 1.10 or greater!
       This function will find the path between two backbone tags"""
    if not skeleton_id and not neuron:
        raise Exception("Must provide skeleton_id or neuron")
    if skeleton_id and not neuron:
        neuron = source.get_neuron(skeleton_id)
    try:
        backbones = neuron.tags['backbone']
    except KeyError:
        print ("Skipping skeleton %s. No Backbones found" % neuron.skeleton_id)
        if 'soma' in neuron.tags:
            print ("Skeleton %s HAS Soma but does not have backbone tag(s)"
                   % neuron.skeleton_id)
        return None
    if len(backbones) < 2:
        print ("Skeleton %s does not have more than 1 backbone tag!"
               % neuron.skeleton_id)
        return None
    elif len(backbones) > 2:
        print ("Skeleton %s has more than 2 backbone tags!"
               % neuron.skeleton_id)
        return None
    backbone_to_backbone = networkx.shortest_path(neuron.graph,
                                                  int(backbones[0]),
                                                  int(backbones[1]))
    return backbone_to_backbone


def find_nearby_points(
        pts, max_dist, return_value=False, include_point=True):
    """
    Finds all points 'near' each point in a point list.

    Points should be an ordered list of node coordinates (like that
    returned from node_array) and contain no branch points

    The distance is not euclidean but is instead distance along
    the path of points
    """
    if return_value:
        rf = lambda i: pts[i]
    else:
        rf = lambda i: i
    npts = []
    md2 = max_dist * max_dist
    # optimized this by precomputing adjacent distances
    # then while walking away from the current point, integrate
    # distance until max_dist exceeded
    dpts = numpy.abs(pts[1:] - pts[:-1]).sum(axis=1)
    for (i, pt) in enumerate(pts):
        # find all 'close' points
        cpts = []
        if include_point:
            cpts.append(rf(i))
        j = 1  # first go positive
        d = 0
        while (i + j) < len(pts):
            d += dpts[i+j-1]
            if d < md2:
                cpts.append(rf(i + j))
            else:
                break
            j += 1
        #while (i + j) < len(pts):
        #    if numpy.abs(pt - pts[i + j]).sum() < md2:
        #        cpts.append(rf(i + j))
        #    else:
        #        break
        #    j += 1
        j = -1
        d = 0
        while (i + j) > -1:
            d += dpts[i+j]
            if d < md2:
                cpts.append(rf(i + j))
            else:
                break
            j -= 1
        #while (i + j) > -1:
        #    if numpy.abs(pt - pts[i + j]).sum() < md2:
        #        cpts.append(rf(i + j))
        #    else:
        #        break
        #    j -= 1
        npts.append(cpts)
    return npts


def gaussian_smooth_points(
        pts, sigma=300., min_effect=1e-6, fix_axes=None):
    if fix_axes is None:
        fix_axes = []
    else:
        fix_axes = [2, ]
    max_dist = numpy.sqrt(
        -numpy.log(min_effect) * 2 * sigma * sigma)
    npts = find_nearby_points(
        pts, max_dist, return_value=True, include_point=False)
    spts = []
    for (i, pt) in enumerate(pts):
        if i == 0 or i == len(pts) - 1 or len(npts[i]) == 0:
            spts.append(pt)
            continue
        # average npts weighted by distance
        deltas = npts[i] - pt
        dists = numpy.linalg.norm(deltas, axis=1)
        # first weight is for pt
        ws = numpy.hstack((
            [1., ], numpy.exp(-(dists ** 2. / (2. * sigma ** 2.)))))
        nws = ws / ws.sum()
        apts = numpy.array([pt, ] + npts[i])
        spt = numpy.sum(apts * nws[:, numpy.newaxis], axis=0)
        for fa in fix_axes:
            spt[fa] = pt[fa]
        spts.append(spt)
    return numpy.array(spts)


def gaussian_smooth_neuron(n, sigma=300., min_effect=1e-6, fix_axes=None):
    """ gaussian smooth a neuron, returning the smoothed skeleton
    to fix specific axes for the smoothed vertices use fix_axes ([2,] for z)
    """
    if fix_axes is None:
        fix_axes = []
    uns = unique_neurites(n)
    sk = copy.deepcopy(n.skeleton)
    for un in uns:
        pts = node_array(n, node_list=un)
        spts = gaussian_smooth_points(pts, sigma, min_effect, fix_axes)
        for i in xrange(len(un)):
            v = sk['vertices'][un[i]]
            s = spts[i]
            v['x'] = s[0]
            v['y'] = s[1]
            v['z'] = s[2]
    return sk
